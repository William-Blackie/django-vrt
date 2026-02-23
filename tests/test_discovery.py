from djvrt.discovery import build_discovered_scenarios, filter_urls


def test_filter_urls_include_and_exclude() -> None:
    urls = [
        "https://example.test/",
        "https://example.test/admin/",
        "https://example.test/about/",
    ]

    filtered = filter_urls(urls, include=[r"^/(|about/)$"], exclude=[r"^/admin"])

    assert filtered == ["https://example.test/", "https://example.test/about/"]


def test_build_discovered_scenarios_deduplicates_ids() -> None:
    urls = [
        "https://example.test/about/",
        "https://example.test/about",
    ]

    scenarios = build_discovered_scenarios(urls)

    assert scenarios[0].id == "about"
    assert scenarios[1].id == "about-2"
