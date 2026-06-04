"""Hello World agent — greets users."""

from datetime import datetime


async def greeter_agent(context: dict, name: str = "World", **kwargs):
    """Greet a user with an emoji.
    
    Args:
        context: Conductor context (user, repo, etc.)
        name: Name to greet
        
    Returns:
        Greeting message with emoji
    """
    emojis = ["👋", "🎉", "✨", "🚀", "💡"]
    emoji = emojis[hash(name) % len(emojis)]
    
    return {
        "agent": "greeter",
        "greeting": f"{emoji} Hello, {name}!",
        "timestamp": datetime.utcnow().isoformat(),
        "context_keys": list(context.keys()),
    }
