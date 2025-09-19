# interactive_cli.py
import asyncio
import getpass
import hashlib
from db import create_admin, get_admin, get_connection

async def delete_admin(username: str) -> bool:
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM scraper_admin WHERE username=%s", (username,))
            return cur.rowcount > 0

async def list_admins():
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT username FROM scraper_admin;")
            return [row["username"] for row in await cur.fetchall()]

async def reset_password(username: str, new_password: str) -> bool:
    new_hash = hashlib.sha256(new_password.encode()).hexdigest()
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE scraper_admin SET password_hash=%s WHERE username=%s",
                (new_hash, username)
            )
            return cur.rowcount > 0

async def main():
    while True:
        print("\n=== Scraper Admin CLI ===")
        print("1. Create admin")
        print("2. Read admin")
        print("3. Delete admin")
        print("4. List admins")
        print("5. Reset password")
        print("6. Exit")
        choice = input("Select an option (1-6): ").strip()

        if choice == "1":
            username = input("Enter username: ").strip()
            password = getpass.getpass("Enter password: ")
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            key1, key2, key3 = await create_admin(username, password_hash)
            print(f"\nAdmin '{username}' created with keys:")
            print(f"key1: {key1}\nkey2: {key2}\nkey3: {key3}")

        elif choice == "2":
            username = input("Enter username to read: ").strip()
            admin = await get_admin(username)
            if admin:
                print("\nAdmin details:")
                print(f"Username: {admin['username']}")
                print(f"Password hash: {admin['password_hash']}")
                print(f"key1: {admin['key1']}\nkey2: {admin['key2']}\nkey3: {admin['key3']}")
            else:
                print(f"\nNo admin found with username '{username}'")

        elif choice == "3":
            username = input("Enter username to delete: ").strip()
            confirm = input(f"Are you sure you want to delete '{username}'? (yes/no): ").strip().lower()
            if confirm == "yes":
                if await delete_admin(username):
                    print(f"\nAdmin '{username}' deleted.")
                else:
                    print(f"\nNo admin found with username '{username}'")
            else:
                print("Delete cancelled.")

        elif choice == "4":
            admins = await list_admins()
            if admins:
                print("\nExisting admins:")
                for u in admins:
                    print(f" - {u}")
            else:
                print("\nNo admins found.")

        elif choice == "5":
            username = input("Enter username to reset password: ").strip()
            new_password = getpass.getpass("Enter new password: ")
            if await reset_password(username, new_password):
                print(f"\nPassword for '{username}' has been reset.")
            else:
                print(f"\nNo admin found with username '{username}'")

        elif choice == "6":
            print("Exiting...")
            break

        else:
            print("Invalid option, please try again.")


if __name__ == "__main__":
    asyncio.run(main())
