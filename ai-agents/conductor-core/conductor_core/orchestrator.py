"""WorkflowOrchestrator — drives the pipeline through workflow stages.

Reads the WorkflowGraph, looks up the agent for each stage from the registry,
runs it via SequentialRunner, and follows the transition based on the decision.

Terminal stage names: "terminal", "escalate_human", "done"
"""

from __future__ import annotations

import structlog

from conductor_core.context import WorkflowContext
from conductor_core.decisions import AgentDecision
from conductor_core.filter_engine import FilterEngine
from conductor_core.graph import WorkflowGraph
from conductor_core.interfaces import IAgent, IResultStore
from conductor_core.router_engine import RouterEngine
from conductor_core.runners.sequential import SequentialRunner
from conductor_core.tracing import get_tracer

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
    ) -> None:
        self._agents = agents
        self._graph = graph
        self._runner = SequentialRunner()
        self._filter_engine = FilterEngine()
        self._router_engine = RouterEngine()
        self._result_store = result_store

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
                        decision = await self._runner.run(agent, context)
                        stage_span.set_attribute("recommendation", decision.recommendation)
                        stage_span.set_attribute("confidence", decision.confidence)
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

