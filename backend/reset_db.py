"""Reset database - drop all tables and recreate from schema."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.connect import get_db_connection


def reset_database():
    """Drop all tables and recreate from schema.sql"""
    
    print("=" * 60)
    print("DATABASE RESET - This will delete ALL data!")
    print("=" * 60)
    
    confirm = input("Are you sure you want to proceed? Type 'YES' to confirm: ")
    if confirm != "YES":
        print("Reset cancelled.")
        return
    
    connection = get_db_connection()
    
    try:
        with connection.cursor() as cursor:
            print("\n🗑️  Dropping existing tables...")
            
            # Drop tables in reverse dependency order
            cursor.execute("DROP TABLE IF EXISTS rule_conflicts CASCADE;")
            print("  - Dropped rule_conflicts")
            
            cursor.execute("DROP TABLE IF EXISTS approval_requests CASCADE;")
            print("  - Dropped approval_requests")
            
            cursor.execute("DROP TABLE IF EXISTS audit_logs CASCADE;")
            print("  - Dropped audit_logs")
            
            cursor.execute("DROP TABLE IF EXISTS commands CASCADE;")
            print("  - Dropped commands")
            
            cursor.execute("DROP TABLE IF EXISTS rules CASCADE;")
            print("  - Dropped rules")
            
            cursor.execute("DROP TABLE IF EXISTS users CASCADE;")
            print("  - Dropped users")
            
        connection.commit()
        print("\n✓ All tables dropped successfully")
        
        # Read and execute schema.sql
        print("\n📋 Creating tables from schema.sql...")
        schema_path = os.path.join(os.path.dirname(__file__), 'db', 'schema.sql')
        
        with open(schema_path, 'r') as f:
            schema_sql = f.read()
        
        with connection.cursor() as cursor:
            cursor.execute(schema_sql)
        
        connection.commit()
        print("✓ Tables created successfully")
        
        print("\n" + "=" * 60)
        print("✅ Database reset complete!")
        print("=" * 60)
        print("\nNext steps:")
        print("  1. Clear frontend config: rm -f ../frontend/.unbound_config.json")
        print("  2. Initialize new user: cd ../frontend && python3 main.py init --username admin")
        print("  3. Seed default rules: python3 seed_rules.py")
        print()
        
    except Exception as exc:
        connection.rollback()
        print(f"\n❌ Error resetting database: {exc}")
        sys.exit(1)
    finally:
        connection.close()


if __name__ == "__main__":
    reset_database()
