import pytest

from gridline.simulation import physics as ph

DT = 1 / 12  # one 5-minute tick in hours


def test_saturation_clamps_rises_with_rain_and_drains() -> None:
    assert ph.step_saturation(0.0, 0.0, k_in=0.35, cut_m=0, dt_h=DT) == 0.0
    assert ph.step_saturation(0.3, 5.0, k_in=0.35, cut_m=0, dt_h=DT) > 0.3
    assert ph.step_saturation(1.0, 500.0, k_in=0.35, cut_m=0, dt_h=DT) == 1.0
    assert ph.step_saturation(0.5, 0.0, k_in=0.35, cut_m=0, dt_h=1.0) < 0.5


def test_open_cut_raises_infiltration() -> None:
    uncut = ph.step_saturation(0.2, 5.0, k_in=0.35, cut_m=0, dt_h=DT)
    cut = ph.step_saturation(0.2, 5.0, k_in=0.35, cut_m=3, dt_h=DT)
    assert cut > uncut


def test_unsupported_cut_is_bench_limited_and_capped_at_soil_depth() -> None:
    assert ph.unsupported_cut_m(1.0, 4.5) == 0.0  # a bench up to 1.5 m stands (permit HT-2026-014 s2)
    assert ph.unsupported_cut_m(3.0, 4.5) == pytest.approx(1.5)
    assert ph.unsupported_cut_m(6.0, 4.5) == pytest.approx(
        3.0
    )  # deeper than the colluvium: no extra soil cut
    assert ph.unsupported_cut_m(35.0, 1.0) == 0.0  # quarry face: the cut is in rock


def test_runoff_flow_increases_with_saturation_and_rain() -> None:
    dry = ph.runoff_flow_m3s(30.0, 0.0, 6.4, 0.36)
    wet = ph.runoff_flow_m3s(30.0, 1.0, 6.4, 0.36)
    assert 0 < dry < wet
    assert wet == pytest.approx(30.0 * 6.4 * ph.MM_H_KM2_TO_M3S * ph.CATCHMENT_ROUTING)
    assert ph.runoff_flow_m3s(0.0, 1.0, 6.4, 0.36) == 0.0


def test_channel_capacity_with_blockage_pumps_and_gate() -> None:
    assert ph.channel_capacity_m3s(27.0, 0.0, 0.0) == 27.0
    assert ph.channel_capacity_m3s(27.0, 0.7, 0.0) == pytest.approx(8.1)
    assert ph.channel_capacity_m3s(27.0, 1.0, 2.4) == pytest.approx(2.4)
    assert ph.channel_capacity_m3s(9.5, 0.05, 0.0, gate_closed=True, pumped=5.0) == pytest.approx(5.0)
    assert ph.channel_capacity_m3s(13.0, 0.12, 0.0, gate_closed=True) == 0.0


def test_water_depth_pools_on_overflow_and_recedes() -> None:
    assert ph.step_water_depth(0.0, 0.0, DT) == 0.0
    assert ph.step_water_depth(0.0, 12.0, DT) > 0
    assert ph.step_water_depth(10.0, 0.0, 1.0) == pytest.approx(10.0 - ph.RECESSION_CM_H)
    shallow_gain = ph.step_water_depth(0.0, 10.0, DT) - 0.0
    deep_gain = ph.step_water_depth(80.0, 10.0, DT) - 80.0
    assert 0 < deep_gain < shallow_gain  # deeper water spreads over more of the flood plain


def test_rating_curve_passes_through_ordinary_and_bankfull() -> None:
    rating = {"ordinary_flow": 85.0, "ordinary_stage": 1.6, "bankfull_flow": 1100.0, "flood_stage": 4.2}
    assert ph.rating_stage_m(85.0, **rating) == pytest.approx(1.6)
    assert ph.rating_stage_m(1100.0, **rating) == pytest.approx(4.2)
    assert ph.rating_stage_m(1700.0, **rating) == pytest.approx(
        5.74, abs=0.01
    )  # HI-2021 record stage was 5.8
    assert ph.rating_stage_m(0.0, **rating) >= 0.0


def test_river_level_approaches_target() -> None:
    level = 1.6
    for _ in range(80):
        level = ph.step_river_level(level, 4.0)
    assert level == pytest.approx(4.0, abs=0.01)
    assert ph.step_river_level(4.0, 1.6) < 4.0


def test_slope_rate_needs_saturation_steepness_and_an_unsupported_cut() -> None:
    assert ph.slope_rate_mm_h(0.5, 32, 3.0) == 0.0
    assert ph.slope_rate_mm_h(1.0, 32, 0.0) == 0.0
    assert ph.slope_rate_mm_h(1.0, 15, 3.0) == 0.0
    shallow = ph.slope_rate_mm_h(1.0, 32, 1.5)
    deep = ph.slope_rate_mm_h(1.0, 32, 3.0)
    assert 0 < shallow < deep
    assert deep / shallow == pytest.approx(4.0)
    assert ph.slope_rate_mm_h(0.9, 32, 3.0) < ph.slope_rate_mm_h(1.0, 32, 3.0)


def test_excavation_advances_only_while_active_and_caps() -> None:
    assert ph.step_excavation(2.5, 6.0, 0.15, DT, active=True) == pytest.approx(2.5 + 0.15 / 12)
    assert ph.step_excavation(2.5, 6.0, 0.15, DT, active=False) == 2.5
    assert ph.step_excavation(5.99, 6.0, 12.0, 1.0, active=True) == 6.0
