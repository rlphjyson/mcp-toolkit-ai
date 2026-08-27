import plistlib
from pathlib import Path


def check_ios_transport_security(project_path: Path) -> dict:
    plist_path = project_path / "ios" / "Runner" / "Info.plist"
    if not plist_path.is_file():
        raise FileNotFoundError(f"Info.plist not found at {plist_path}")

    with plist_path.open("rb") as f:
        data = plistlib.load(f)

    ats = data.get("NSAppTransportSecurity")
    if not isinstance(ats, dict):
        return {
            "ats_configured": False,
            "allows_arbitrary_loads": False,
            "insecure_domain_exceptions": [],
        }

    insecure_domains = []
    exception_domains = ats.get("NSExceptionDomains")
    if isinstance(exception_domains, dict):
        insecure_domains = [
            domain
            for domain, domain_config in exception_domains.items()
            if isinstance(domain_config, dict)
            and domain_config.get("NSExceptionAllowsInsecureHTTPLoads") is True
        ]

    return {
        "ats_configured": True,
        "allows_arbitrary_loads": ats.get("NSAllowsArbitraryLoads") is True,
        "insecure_domain_exceptions": insecure_domains,
    }
