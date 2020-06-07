import os

def engineering_mode_enabled(): 
  engineering_mode = "False"

  flag_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), "engineering_mode.txt")
  with open(flag_file, "a+") as file:
    engineering_mode = file.read().strip()
        
  return engineering_mode in ["on", "True", "true", "yes"]

