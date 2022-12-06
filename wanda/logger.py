
class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

class Logger:

    def __init__(self, name):
        self.name = name

    def warning(self, text):
        print(bcolors.FAIL + f"Warning: {text}" + bcolors.ENDC)

    def error(self, text):
        print(bcolors.FAIL + f"Error: {text}" + bcolors.ENDC)

    def info(self, text):
        print(bcolors.OKGREEN + f"Info: {text}" + bcolors.ENDC)

    def hint(self, text):
        print(bcolors.OKCYAN + f"{text}" + bcolors.ENDC)
