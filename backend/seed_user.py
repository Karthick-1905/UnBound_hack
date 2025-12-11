#!/usr/bin/env python3
"""Create a default member user for testing purposes."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.users import create_user, UsernameAlreadyExistsError


def create_default_member():
    """Create a default member user with junior tier."""
    
    username = "testuser"
    email = "testuser@example.com"
    user_tier = "junior"
    
    print("=" * 60)
    print("Creating Default Member User")
    print("=" * 60)
    
    try:
        user, api_key = create_user(
            username=username,
            email=email,
            role="member",
            user_tier=user_tier
        )
        
        print(f"\n✅ User created successfully!")
        print(f"\n{'='*60}")
        print("USER DETAILS")
        print("="*60)
        print(f"Username:      {user.username}")
        print(f"User ID:       {user.id}")
        print(f"Role:          {user.role}")
        print(f"Tier:          {user.user_tier}")
        print(f"Credits:       {user.credit_balance}")
        print(f"\n{'='*60}")
        print("API KEY (save this - it won't be shown again!)")
        print("="*60)
        print(f"{api_key}")
        print("="*60)
        
        print("\n📝 Save this configuration to frontend/.unbound_config.json:")
        print("-" * 60)
        print(f'''{{
  "api_key": "{api_key}",
  "base_url": "http://localhost:8000"
}}''')
        print("-" * 60)
        
    except UsernameAlreadyExistsError:
        print(f"\n⚠️  User '{username}' already exists.")
        print("Delete the user first or use a different username.")
        sys.exit(1)
    except Exception as exc:
        print(f"\n❌ Error creating user: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    create_default_member()
