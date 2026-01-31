from __future__ import annotations

from mac_health_checkup.diagnostics.thermals import _parse_powermetrics_smc, _parse_temperature_lines


def test_parse_powermetrics_smc_extracts_temps_and_fans() -> None:
    raw = """
    SMC sensors:
    CPU Core Average: 58.2 C
    GPU Clusters Average: 53.0°C
    Fan 0: 1358 RPM
    Fan 1: 1400 RPM
    """
    temps, fans = _parse_powermetrics_smc(raw)
    assert len(temps) == 2
    assert temps[0].label == "CPU Core Average"
    assert temps[0].celsius == 58.2
    assert temps[1].label == "GPU Clusters Average"
    assert temps[1].celsius == 53.0

    assert [fan.label for fan in fans] == ["Fan 0", "Fan 1"]
    assert [fan.rpm for fan in fans] == [1358, 1400]


def test_parse_powermetrics_smc_dedupes_and_sorts() -> None:
    raw = """
    CPU Core Average: 50 C
    CPU Core Average: 51 C
    GPU: 60 C
    Fan: 1000 RPM
    Fan: 1001 RPM
    """
    temps, fans = _parse_powermetrics_smc(raw)
    assert [temp.label for temp in temps] == ["GPU", "CPU Core Average"]
    assert [fan.rpm for fan in fans] == [1000]


def test_parse_temperature_lines_extracts_generic_sensor_rows() -> None:
    raw = """
    Airport Proximity: 40 C
    Battery: 32°C
    CPU Core Average: 58.2 C
    """
    temps = _parse_temperature_lines(raw)
    assert temps[0].label == "CPU Core Average"
    assert temps[0].celsius == 58.2
    assert temps[-1].label == "Battery"
