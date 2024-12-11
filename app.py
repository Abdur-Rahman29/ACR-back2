import subprocess
import os

if __name__ == "__main__":
    # Get the absolute path to the ReviewBot directory
    reviewbot_dir = os.path.join(os.getcwd(), "ReviewBot")  # Get the full path to the ReviewBot directory
    
    # Check if the directory exists
    if os.path.isdir(reviewbot_dir):
        # Run the Django development server in the ReviewBot directory
        subprocess.run(["python", "manage.py", "runserver"."127.0.0.1:8080"], cwd=reviewbot_dir)
    else:
        print(f"Error: The directory '{reviewbot_dir}' does not exist.")
