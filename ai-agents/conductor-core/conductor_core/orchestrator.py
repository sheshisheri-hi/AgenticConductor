"""WorkflowOrchestrator — drives the pipeline through workflow stages.

Reads the WorkflowGraph, looks up the agent for each stage from the registry,
runs it via SequentialRunner, and follows the transition based on the decision.

Integrates with ConductorManifest for agent discovery, HookEngine for lifecycle
hooks, PolicyResolver for multi-source config merging, and SecretDetector for
security gates.

Terminal stage names: "terminal", "escalate_human", "done"
"""

from __future__ import annotations

from pathlib import Path
import structlog

from conductor_core.context import WorkflowContext
from conductor_core.decisions import AgentDecision
from conductor_core.filter_engine import FilterEngine
from conductor_core.graph import WorkflowGraph
from conductor_core.interfaces import IAgent, IResultStore
from conductor_core.router_engine import RouterEngine
from conductor_core.runners.sequential import SequentialRunner
from conductor_core.tracing import get_tracer
from conductor_core.manifest import ConductorManifest
from conductor_core.agent_registry import AgentRegistry
from conductor_core.hooks.engine import HookEngine
from conductor_core.hooks.policy import PolicyResolver
from conductor_core.hooks.types import HookEvent, HookPayload
from conductor_core.security.secret_detector import SecretDetector
import time

logger = structlog.get_logger(__name__)

TERMINAL_STAGES = {"terminal", "escalate_human", "done", ""}


class WorkflowOrchestrator:
    """Drives a WorkflowContext through the stages defined in WorkflowGraph.

    Usage:
        orchestrator = WorkflowOrchestrator(
            agents={"triage": MyTriageAgent(llm), "reviewer": ReviewerAgent(llm)},
            graph=WorkflowGraph.from_yaml("workflow.yaml"),
            result_store=SQLiteResultStore(),  # any IResultStore impl — SQLite (dev) or Postgres (prod)
        )
        result = await orchestrator.run(context)
    """

    def __init__(
        self,
        agents: dict[str, IAgent],
        graph: WorkflowGraph,
        result_store: IResultStore | None = None,
        hook_engine: HookEngine | None = None,
        policy_resolver: PolicyResolver | None = None,
        secret_detector: SecretDetector | None = None,
    ) -> None:
        self._agents = agents
        self._graph = graph
        self._runner = SequentialRunner()
        self._filter_engine = FilterEngine()
        self._router_engine = RouterEngine()
        self._result_store = result_store
        self._hook_engine = hook_engine or HookEngine()
        self._policy_resolver = policy_resolver or PolicyResolver()
        self._secret_detector = secret_detector or SecretDetector()

    @classmethod
    async def from_manifest(
        cls,
        manifest_path: str | Path,
        result_store: IResultStore | None = None,
    ) -> WorkflowOrchestrator:
        """Load orchestrator from conductor.json manifest.

        Args:
            manifest_path: Path to conductor.json
            result_store: Optional result store (SQLite/Postgres)

        Returns:
            Fully configured WorkflowOrchestrator with agents, hooks, security

        Raises:
            FileNotFoundError: If manifest not found
            ValueError: If manifest validation fails
        """
        manifest_path = Path(manifest_path)
        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest not found: {manifest_path}")

        # Load manifest + agents
        manifest = ConductorManifest.load(manifest_path)
        registry = AgentRegistry()
        agents = registry.discover(manifest.agents_paths, manifest.disabled_agents)

        # Load workflow graph
        workflow_path = manifest_path.parent / manifest.workflow_path
        graph = WorkflowGraph.from_yaml(str(workflow_path))

        # Load hooks + policies
        hook_engine = HookEngine()
        if manifest.hooks:
            hook_engine.load(manifest.hooks)

        policy_resolver = PolicyResolver()
        # Load policies from manifest + .conductor/policies/
        if manifest.policies:
            policy_resolver.load_policy(manifest.policies, source="manifest")

        # Create secret detector
        secret_detector = SecretDetector()

        logger.info(
            "orchestrator_loaded_from_manifest",
            manifest_path=str(manifest_path),
            agents_discovered=len(agents),
            hooks_configured=len(manifest.hooks) if manifest.hooks else 0,
        )

        return cls(
            agents=agents,
            graph=graph,
            result_store=result_store,
            hook_engine=hook_engine,
            policy_resolver=policy_resolver,
            secret_detector=secret_detector,
        )

    async def run(
        self,
        context: WorkflowContext,
        mode: str | None = None,
    ) -> WorkflowContext:
        """Execute the workflow from the first stage to terminal.

        Args:
            context: WorkflowContext to drive through the pipeline.
            mode: Override mode ('plan' or 'execute'). If None, uses graph.mode.

        Returns:
            Final WorkflowContext after the pipeline completes.
        """
        effective_mode = mode or self._graph.mode
        context.mode = effective_mode  # type: ignore[assignment]
        context.workflow_name = self._graph.name
        tracer = get_tracer("conductor.orchestrator")

        with tracer.start_as_current_span(f"workflow:{self._graph.name}") as workflow_span:
            workflow_span.set_attribute("run_id", context.run_id)
            workflow_span.set_attribute("mode", effective_mode)
            workflow_span.set_attribute("workflow", self._graph.name)

            logger.info(
                "orchestrator_start",
                run_id=context.run_id,
                workflow=self._graph.name,
                mode=effective_mode,
            )

            # --- Fire runStart hook (fail-open) ---
            try:
                # Extract source from payload if available
                source = ""
                if isinstance(context.payload, dict):
                    source = context.payload.get("source", "")
                
                payload = HookPayload(
                    run_id=context.run_id,
                    timestamp=int(time.time() * 1000),
                    workflow_name=self._graph.name,
                    mode=effective_mode,
                    source=source,
                )
                self._hook_engine.fire(HookEvent.RUN_START, payload)
            except Exception as e:
                logger.warning("hook_runStart_failed", run_id=context.run_id, error=str(e))

            # --- Filter pass (zero LLM cost) ---
            if self._graph.filters:
                filter_result = self._filter_engine.evaluate(context.payload, self._graph.filters)
                if filter_result.rejected:
                    logger.info(
                        "workflow_filtered",
                        run_id=context.run_id,
                        reason=filter_result.reason,
                    )
                    context.mark_blocked(f"Filtered: {filter_result.reason}")
                    workflow_span.set_attribute("filtered", True)
                    workflow_span.set_attribute("filter_reason", filter_result.reason)
                    await self._persist(context)
                    return context

            # --- Route selection ---
            if self._graph.routes:
                try:
                    route = self._router_engine.route(context.payload, self._graph.routes)
                    context.pipeline_route = route
                    logger.info("workflow_routed", run_id=context.run_id, route=route)
                    workflow_span.set_attribute("route", route)
                except Exception as e:
                    logger.warning("routing_failed", run_id=context.run_id, error=str(e))

            # --- Stage execution loop ---
            current_stage = self._graph.first_stage()
            saved_count = 0

            while current_stage and current_stage.name not in TERMINAL_STAGES:
                context.current_stage = current_stage.name

                # Plan mode gate — stop before stages marked stop_before
                if effective_mode == "plan" and current_stage.stop_before:
                    logger.info(
                        "plan_mode_halt",
                        run_id=context.run_id,
                        stage=current_stage.name,
                    )
                    break

                # Check if this stage is a parallel group trigger
                parallel_group = self._graph.get_parallel_group(current_stage.name)
                if parallel_group:
                    from conductor_core.runners.parallel import ParallelRunner, MergeStrategy
                    parallel_runner = ParallelRunner(MergeStrategy(parallel_group.merge_strategy))
                    agents_to_run = []
                    missing_agent = None
                    for agent_name in parallel_group.agents:
                        a = self._agents.get(agent_name)
                        if a is None:
                            logger.warning("parallel_agent_not_found", agent=agent_name)
                            missing_agent = agent_name
                            break
                        agents_to_run.append(a)

                    if missing_agent is not None:
                        context.mark_blocked(f"Parallel agent not registered: {missing_agent!r}")
                        workflow_span.set_attribute("blocked", True)
                        break

                    with tracer.start_as_current_span(f"stage:{current_stage.name}") as stage_span:
                        stage_span.set_attribute("parallel", True)
                        stage_span.set_attribute("run_id", context.run_id)
                        try:
                            all_decisions = await parallel_runner.run(agents_to_run, context)
                            decision = parallel_runner.merge(all_decisions)
                            context.append_decision(decision)
                            stage_span.set_attribute("recommendation", decision.recommendation)
                            stage_span.set_attribute("confidence", decision.confidence)
                        except Exception as e:
                            logger.error("parallel_stage_failed", stage=current_stage.name, error=str(e))
                            context.mark_blocked(f"Parallel stage {current_stage.name} failed: {e}")
                            stage_span.record_exception(e)
                            stage_span.set_attribute("error", True)
                            break

                    for d in context.decisions[saved_count:]:
                        await self._save_decision(context.run_id, d, current_stage.name)
                    saved_count = len(context.decisions)

                    next_stage_name = (
                        parallel_group.next_stage_on_pass
                        if decision.recommendation != "block"
                        else parallel_group.next_stage_on_block
                    )
                    logger.info(
                        "parallel_stage_transition",
                        run_id=context.run_id,
                        from_stage=current_stage.name,
                        to_stage=next_stage_name,
                        recommendation=decision.recommendation,
                    )

                    if next_stage_name in TERMINAL_STAGES:
                        break

                    current_stage = self._graph.get_stage(next_stage_name)
                    if current_stage is None:
                        logger.warning("stage_not_found", stage=next_stage_name)
                        break
                    continue

                # Regular single-agent stage
                agent = self._agents.get(current_stage.agent)
                if agent is None:
                    logger.error(
                        "agent_not_found",
                        stage=current_stage.name,
                        agent_key=current_stage.agent,
                        registered=list(self._agents.keys()),
                    )
                    context.mark_blocked(f"No agent registered for: {current_stage.agent!r}")
                    workflow_span.set_attribute("blocked", True)
                    break

                # Apply YAML stage-level model override (highest priority)
                if hasattr(agent, "_runtime_model"):
                    agent._runtime_model = current_stage.model  # type: ignore[union-attr]

                with tracer.start_as_current_span(f"stage:{current_stage.name}") as stage_span:
                    stage_span.set_attribute("agent", current_stage.agent)
                    stage_span.set_attribute("run_id", context.run_id)
                    try:
                        # --- Security: Scan input for secrets (fail-closed) ---
                        try:
                            self._secret_detector.scan_input(context.payload)
                        except ValueError as e:
                            logger.error(
                                "secret_detected_input",
                                stage=current_stage.name,
                                agent=current_stage.agent,
                                error=str(e),
                            )
                            context.mark_blocked(f"Secret detected in input: {e}")
                            stage_span.set_attribute("secret_detected", True)
                            break

                        # --- Fire preAgentRun hook (fail-closed) ---
                        try:
                            # Extract source from payload if available
                            source = ""
                            if isinstance(context.payload, dict):
                                source = context.payload.get("source", "")
                            
                            payload = HookPayload(
                                run_id=context.run_id,
                                timestamp=int(time.time() * 1000),
                                workflow_name=self._graph.name,
                                mode=effective_mode,
                                source=source,
                                agent_name=current_stage.agent,
                                stage_name=current_stage.name,
                            )
                            self._hook_engine.fire(HookEvent.PRE_AGENT_RUN, payload)
                        except Exception as e:
                            logger.error(
                                "hook_preAgentRun_failed",
                                stage=current_stage.name,
                                agent=current_stage.agent,
                                error=str(e),
                            )
                            context.mark_blocked(f"preAgentRun hook failed: {e}")
                            stage_span.set_attribute("preagent_hook_failed", True)
                            break

                        # --- Run agent ---
                        decision = await self._runner.run(agent, context)
                        stage_span.set_attribute("recommendation", decision.recommendation)
                        stage_span.set_attribute("confidence", decision.confidence)

                        # --- Security: Scan output for secrets (fail-closed) ---
                        try:
                            decision_dict = {
                                "output": decision.__dict__,
                                "recommendation": decision.recommendation,
                                "reasoning": decision.reasoning,
                                "evidence": decision.evidence,
                            }
                            self._secret_detector.scan_output(decision_dict)
                        except ValueError as e:
                            logger.error(
                                "secret_detected_output",
                                stage=current_stage.name,
                                agent=current_stage.agent,
                                error=str(e),
                            )
                            # Redact the decision before marking blocked
                            context.mark_blocked(f"Secret detected in output: {e}")
                            stage_span.set_attribute("secret_detected", True)
                            break

                        # --- Fire postAgentRun hook (fail-open) ---
                        try:
                            # Extract source from payload if available
                            source = ""
                            if isinstance(context.payload, dict):
                                source = context.payload.get("source", "")
                            
                            payload = HookPayload(
                                run_id=context.run_id,
                                timestamp=int(time.time() * 1000),
                                workflow_name=self._graph.name,
                                mode=effective_mode,
                                source=source,
                                agent_name=current_stage.agent,
                                stage_name=current_stage.name,
                                recommendation=decision.recommendation,
                                confidence=decision.confidence,
                            )
                            self._hook_engine.fire(HookEvent.POST_AGENT_RUN, payload)
                        except Exception as e:
                            logger.warning(
                                "hook_postAgentRun_failed",
                                stage=current_stage.name,
                                agent=current_stage.agent,
                                error=str(e),
                            )
                            # Fail-open: continue despite hook failure
                    except Exception as e:
                        logger.error("stage_failed", stage=current_stage.name, error=str(e))
                        context.mark_blocked(f"Stage {current_stage.name} failed: {e}")
                        stage_span.record_exception(e)
                        stage_span.set_attribute("error", True)
                        break

                for d in context.decisions[saved_count:]:
                    await self._save_decision(context.run_id, d, current_stage.name)
                saved_count = len(context.decisions)

                next_stage_name = self._resolve_next(current_stage, decision)
                logger.info(
                    "stage_transition",
                    run_id=context.run_id,
                    from_stage=current_stage.name,
                    to_stage=next_stage_name,
                    recommendation=decision.recommendation,
                )

                if next_stage_name in TERMINAL_STAGES:
                    break

                current_stage = self._graph.get_stage(next_stage_name)
                if current_stage is None:
                    logger.warning("stage_not_found", stage=next_stage_name)
                    break

            workflow_span.set_attribute("blocked", context.blocked)
            workflow_span.set_attribute("decision_count", len(context.decisions))
            workflow_span.set_attribute("total_tokens", context.telemetry.total_tokens)

        # --- Fire runEnd hook (fail-open) ---
        try:
            # Extract source from payload if available
            source = ""
            if isinstance(context.payload, dict):
                source = context.payload.get("source", "")
            
            payload = HookPayload(
                run_id=context.run_id,
                timestamp=int(time.time() * 1000),
                workflow_name=self._graph.name,
                mode=effective_mode,
                source=source,
            )
            self._hook_engine.fire(HookEvent.RUN_END, payload)
        except Exception as e:
            logger.warning("hook_runEnd_failed", run_id=context.run_id, error=str(e))

        logger.info(
            "orchestrator_complete",
            run_id=context.run_id,
            blocked=context.blocked,
            decisions=len(context.decisions),
            total_tokens=context.telemetry.total_tokens,
        )
        await self._persist(context)
        return context

    async def _persist(self, context: WorkflowContext) -> None:
        """Save run to result store if one is configured."""
        if self._result_store is None:
            return
        try:
            await self._result_store.save_run(context)
        except Exception as e:
            logger.warning("result_store_save_failed", run_id=context.run_id, error=str(e))

    async def _save_decision(self, run_id: str, decision: AgentDecision, stage: str) -> None:
        if self._result_store is None:
            return
        try:
            await self._result_store.save_decision(run_id, decision, stage)
        except Exception as e:
            logger.warning("save_decision_failed", run_id=run_id, error=str(e))

    def _resolve_next(self, stage, decision: AgentDecision) -> str:
        """Resolve the next stage name from the decision recommendation."""
        rec = decision.recommendation
        if rec == "proceed":
            return stage.on_proceed
        elif rec in ("block", "request_another_round"):
            return stage.on_block
        elif rec == "escalate":
            return stage.on_escalate
        elif rec == "plan_only":
            return stage.on_plan_only
        else:
            return stage.on_proceed

