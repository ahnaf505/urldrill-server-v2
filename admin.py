# interactive_cli.py
from db import create_admin, get_admin, delete_admin
from passlib.hash import sha256_crypt
import getpass
from db import *

def main():
    while True:
        print("\n=== Scraper Admin CLI ===")
        print("1. Create admin")
        print("2. Read admin")
        print("3. Delete admin")
        print("4. Exit")
        choice = input("Select an option (1-4): ").strip()

        if choice == "1":
            username = input("Enter username: ").strip()
            password = getpass.getpass("Enter password: ")
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            key1, key2, key3 = create_admin(username, password_hash)
            print(f"Admin '{username}' created with keys:")
            print(f"key1: {key1}\nkey2: {key2}\nkey3: {key3}")

        elif choice == "2":
            username = input("Enter username to read: ").strip()
            admin = get_admin(username)
            if admin:
                print("Admin details:")
                print(f"Username: {admin[0]}")
                print(f"Password hash: {admin[1]}")
                print(f"key1: {admin[2]}\nkey2: {admin[3]}\nkey3: {admin[4]}")
            else:
                print(f"No admin found with username '{username}'")

        elif choice == "3":
            username = input("Enter username to delete: ").strip()
            confirm = input(f"Are you sure you want to delete '{username}'? [y/N]: ").lower()
            if confirm == "y":
                delete_admin(username)
                print(f"Admin '{username}' deleted")
            else:
                print("Delete cancelled")

        elif choice == "4":
            print("Exiting...")
            break

        else:
            print("Invalid option, please try again.")


if __name__ == "__main__":
    main()
