#!/usr/bin/env python3
"""Hello World Conductor Example.

Minimal working example showing how to:
1. Create a conductor.json manifest
2. Write an agent
3. Call the agent from main()

Run:
    python main.py
    python main.py --name Alice
    python main.py --plan  (show plan without executing)
"""

import asyncio
import argparse
import json
from pathlib import Path
from datetime import datetime

from agents.greeter import greeter_agent


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Hello World Conductor Example")
    parser.add_argument("--name", default="World", help="Name to greet")
    parser.add_argument("--plan", action="store_true", help="Show plan without executing")
    parser.add_argument("--log", default="logs/hello-world.log", help="Log file path")
    
    args = parser.parse_args()
    
    # Load conductor.json
    manifest_path = Path(__file__).parent / "conductor.json"
    with open(manifest_path) as f:
        manifest = json.load(f)
    
    print(f"{'='*60}")
    print(f"Conductor: {manifest['name']} v{manifest['version']}")
    print(f"{'='*60}\n")
    
    # Create execution context
    context = {
        "run_id": f"HELLO-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}",
        "user": "developer",
        "mode": "plan" if args.plan else "execute",
    }
    
    print(f"📋 Plan: Call greeter_agent with name='{args.name}'")
    print(f"   Context: {context}\n")
    
    if args.plan:
        print("✋ PLAN MODE — Not executing (use --execute to run)\n")
        return
    
    print("▶️  Executing agent...\n")
    
    # Call agent
    result = await greeter_agent(context=context, name=args.name)
    
    # Display result
    print(f"✅ Success!")
    print(f"   Greeting: {result['greeting']}")
    print(f"   Timestamp: {result['timestamp']}")
    print(f"   Context keys: {result['context_keys']}\n")
    
    # Save to log
    log_path = Path(args.log)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(log_path, "a") as f:
        f.write(f"{context['run_id']} | {result['greeting']} | {result['timestamp']}\n")
    
    print(f"📝 Logged to {log_path}")
    print(f"\n{'='*60}")
    print("✨ You've built your first Conductor app! Next steps:")
    print("   1. Read QUICKSTART.md for API overview")
    print("   2. Check samples/security-remediation/ for production pipeline")
    print("   3. Add your own agents in agents/ directory")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(main())
