import pytest

from wanda.autonomous_system.autonomous_system import AutonomousSystem


@pytest.mark.unit
class TestAutonomousSystem:

    @pytest.mark.parametrize(
        "asn,name,irr_names,expected_irr_names",
        [
            (9136, "WOBCOM", "AS-WOBCOM", ["AS-WOBCOM"]),
            (208395, "WDZ", "", ["AS208395"]),
            (1299, "Twelve99", "RIPE::AS-TELIANET RIPE::AS-TELIANET-V6", ["AS-TELIANET", "AS-TELIANET-V6"])
        ]
    )
    def test_irr_name(self, asn, name, irr_names, expected_irr_names):
        autos = AutonomousSystem(
            asn=asn,
            name=name,
            irr_as_set=irr_names
        )

        irr_names_set = set(autos.get_irr_names())
        expected_irr_names_set = set(expected_irr_names)

        assert len(irr_names_set) > 0
        assert irr_names_set == expected_irr_names_set
