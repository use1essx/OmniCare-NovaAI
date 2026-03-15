#!/usr/bin/env python3
"""
Create or update super admin user with bcrypt password.

Usage (from Docker):
    docker exec healthcare_ai_backend python /app/scripts/create_super_admin.py

Usage (with custom password):
    docker exec healthcare_ai_backend python /app/scripts/create_super_admin.py --password YOUR_PASSWORD

Usage (with custom username):
    docker exec healthcare_ai_backend python /app/scripts/create_super_admin.py --username admin --password admin123
"""

import argparse
import asyncio
import os
import sys

sys.path.insert(0, '/app')

from src.security.auth import get_password_hash, verify_password


async def create_admin(username: str = 'admin', password: str = 'admin', email: str = None):
    """Create or update admin user with bcrypt password."""
    import asyncpg
    
    if email is None:
        email = f'{username}@healthcare.ai'
    
    # Generate bcrypt hash
    new_hash = get_password_hash(password)
    print(f'Generated bcrypt hash for password')
    print(f'Verification test: {verify_password(password, new_hash)}')
    
    # Try multiple passwords for database connection (in case volume was created with different password)
    db_password = os.environ.get('DATABASE_PASSWORD', 'CHANGE_IN_PRODUCTION')
    passwords_to_try = [db_password, 'admin', 'CHANGE_IN_PRODUCTION']
    
    conn = None
    for pwd in passwords_to_try:
        try:
            conn = await asyncpg.connect(
                host=os.environ.get('DATABASE_HOST', 'postgres'),
                port=int(os.environ.get('DATABASE_PORT', '5432')),
                database=os.environ.get('DATABASE_NAME', 'healthcare_ai_v2'),
                user=os.environ.get('DATABASE_USER', 'admin'),
                password=pwd
            )
            break
        except asyncpg.exceptions.InvalidPasswordError:
            continue
    
    if conn is None:
        print('ERROR: Could not connect to database')
        print('Try running: docker exec healthcare_ai_postgres psql -U admin -d healthcare_ai_v2')
        return False
    
    try:
        # Check if user exists
        existing = await conn.fetchrow(
            'SELECT id, username, email FROM users WHERE username = $1',
            username
        )
        
        if existing:
            # Update existing user
            await conn.execute('''
                UPDATE users SET 
                    hashed_password = $1,
                    email = $2,
                    is_active = true,
                    is_verified = true,
                    is_admin = true,
                    is_super_admin = true,
                    role = 'super_admin',
                    failed_login_attempts = 0,
                    account_locked_until = NULL,
                    updated_at = NOW()
                WHERE username = $3
            ''', new_hash, email, username)
            print(f'Updated existing user: {username}')
        else:
            # Create new user
            await conn.execute('''
                INSERT INTO users (
                    email, username, hashed_password, full_name,
                    is_active, is_verified, is_admin, is_super_admin,
                    role, failed_login_attempts, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, true, true, true, true, 'super_admin', 0, NOW(), NOW())
            ''', email, username, new_hash, 'System Administrator')
            print(f'Created new user: {username}')
        
        # Verify
        user = await conn.fetchrow(
            'SELECT id, username, email, role, is_super_admin, is_active FROM users WHERE username = $1',
            username
        )
        
        print('')
        print('=' * 50)
        print('       SUPER ADMIN USER READY')
        print('=' * 50)
        print(f'  ID:         {user["id"]}')
        print(f'  Username:   {user["username"]}')
        print(f'  Email:      {user["email"]}')
        print(f'  Role:       {user["role"]}')
        print(f'  Super Admin: {user["is_super_admin"]}')
        print(f'  Active:     {user["is_active"]}')
        print('')
        print(f'  Password:   {password}')
        print('')
        print('  Login URL:  http://localhost:8000/live2d/auth')
        print('')
        print('  WARNING: Change password in production!')
        print('=' * 50)
        
        return True
        
    finally:
        await conn.close()


def main():
    parser = argparse.ArgumentParser(description='Create or update super admin user')
    parser.add_argument('--username', '-u', default='admin', help='Admin username (default: admin)')
    parser.add_argument('--password', '-p', default='admin', help='Admin password (default: admin)')
    parser.add_argument('--email', '-e', default=None, help='Admin email (default: username@healthcare.ai)')
    
    args = parser.parse_args()
    
    success = asyncio.run(create_admin(args.username, args.password, args.email))
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
