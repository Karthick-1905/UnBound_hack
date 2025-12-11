"""Seed the database with default rules."""

import sys
import os

# Add the backend directory to the path so we can import services
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.rules import create_rule, RuleValidationError, RuleCreationError


DEFAULT_RULES = [
    {
        "pattern": r":\(\)\{\s*:\|:&\s*\};:",
        "action": "AUTO_REJECT",
        "description": "Block fork bomb"
    },
    {
        "pattern": r"rm\s+-rf\s+/",
        "action": "AUTO_REJECT",
        "description": "Block recursive root deletion"
    },
    {
        "pattern": r"mkfs\.",
        "action": "AUTO_REJECT",
        "description": "Block filesystem formatting"
    },
    {
        "pattern": r"git\s+",
        "action": "AUTO_REJECT",
        "description": "Block all git commands"
    },
    {
        "pattern": r"^(ls|cat|pwd|echo)(\s|$)",
        "action": "AUTO_ACCEPT",
        "description": "Allow basic read-only commands"
    },
]


def seed_rules():
    """Seed the database with default rules."""
    
    print("Seeding default rules...")
    
    for rule_data in DEFAULT_RULES:
        try:
            rule = create_rule(
                pattern=rule_data["pattern"],
                action=rule_data["action"],
                description=rule_data["description"]
            )
            print(f"✓ Created rule: {rule.description} (ID: {rule.id})")
        except RuleValidationError as exc:
            print(f"✗ Validation error for pattern '{rule_data['pattern']}': {exc}")
        except RuleCreationError as exc:
            print(f"✗ Failed to create rule '{rule_data['description']}': {exc}")
    
    print("\nSeeding complete!")


if __name__ == "__main__":
    seed_rules()
