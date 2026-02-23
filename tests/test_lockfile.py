from djvrt.lockfile import build_lockfile
from djvrt.models import AuthProfile, DiscoveredScenario, DJVRTConfig, ExperimentVariant, Viewport


def test_lockfile_matrix_is_deterministic() -> None:
    config = DJVRTConfig(
        base_url="http://example.test",
        viewports=[
            Viewport(name="desktop", width=1200, height=800),
            Viewport(name="mobile", width=390, height=844),
        ],
        auth_profiles=[
            AuthProfile(name="anonymous"),
            AuthProfile(name="staff", storage_state=".auth/staff.json"),
        ],
    )

    scenarios = [
        DiscoveredScenario(id="home", url="/", viewports=["desktop"], auth_profiles=["anonymous"]),
        DiscoveredScenario(id="about", url="/about/"),
    ]

    first = build_lockfile(config, scenarios)
    second = build_lockfile(config, scenarios)

    assert first.hash == second.hash
    assert len(first.scenarios) == 5
    assert all(scenario.url.startswith("http://example.test") for scenario in first.scenarios)
    assert {scenario.experiment_name for scenario in first.scenarios} == {"control"}


def test_lockfile_expands_experiment_variants() -> None:
    config = DJVRTConfig(
        base_url="http://example.test",
        viewports=[Viewport(name="desktop", width=1200, height=800)],
        auth_profiles=[AuthProfile(name="anonymous", headers={"X-Auth": "anon"})],
        experiments=[
            ExperimentVariant(name="control"),
            ExperimentVariant(
                name="variant-a",
                query_params={"exp_banner": "variant-a"},
                headers={"X-Experiment": "variant-a"},
            ),
        ],
    )

    scenarios = [DiscoveredScenario(id="home", url="/", experiments=["control", "variant-a"])]
    lockfile = build_lockfile(config, scenarios)

    assert len(lockfile.scenarios) == 2
    experiment_names = {scenario.experiment_name for scenario in lockfile.scenarios}
    assert experiment_names == {"control", "variant-a"}

    variant = next(scenario for scenario in lockfile.scenarios if scenario.experiment_name == "variant-a")
    assert "exp_banner=variant-a" in variant.url
    assert variant.headers["X-Auth"] == "anon"
    assert variant.headers["X-Experiment"] == "variant-a"
