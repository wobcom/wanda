import re


class AutonomousSystem:
    def __init__(self, asn, name, irr_as_set):
        self.asn = asn
        self.name = name
        self.irr_as_set = irr_as_set

    def __eq__(self, other):
        return self.asn == other.asn

    def __hash__(self):
        return hash(self.asn)

    def __str__(self):
        return f"{self.name} (AS{self.asn})"

    def get_irr_names(self):

        return_elements = []

        if self.irr_as_set:
            set_elements = self.irr_as_set.upper().split(" ")
            for set_element in set_elements:
                match_result = re.findall(r'(AS[^\s,]*)', set_element)

                if len(match_result) != 0:
                    return_elements.append(match_result[0])

        # Note: If there is no IRR names, we fall back to AS1234, but we do this later in the code.

        return return_elements
