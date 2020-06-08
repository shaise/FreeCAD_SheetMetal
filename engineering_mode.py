import os

def engineering_mode_enabled(): 
    flag_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), "engineering-mode-enabled.txt")
    try: 
        with open(flag_file, "r") as file:
            engineering_mode = True
    except:
        engineering_mode = False
    
    return engineering_mode

