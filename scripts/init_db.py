"""Initialize database directories and structure"""
import os

dirs = ["data/cache", "memory", "logs"]
for d in dirs:
    os.makedirs(d, exist_ok=True)
    gitkeep = os.path.join(d, ".gitkeep")
    with open(gitkeep, "w") as f:
        pass
print("Directories initialized:", dirs)
