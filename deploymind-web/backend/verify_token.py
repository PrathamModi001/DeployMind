"""Quick script to verify GitHub token is saved after re-login."""
from api.services.database import get_db
from api.models.user import User

db = next(get_db())
user = db.query(User).filter(User.username == "PrathamModi001").first()

if user:
    print(f"Username: {user.username}")
    print(f"Email: {user.email}")

    if user.github_access_token:
        print(f"[OK] GitHub Token: SET ({user.github_access_token[:20]}...)")
        print("\nYou can now test the repository dropdown!")
        print("Go to: http://localhost:5000/dashboard/deployments/new")
    else:
        print("[ERROR] GitHub Token: NOT SET (NULL)")
        print("\nYou MUST log out and log back in via GitHub to save your token.")
        print("Current session is using old JWT - OAuth callback hasn't fired yet.")
else:
    print("User not found")
