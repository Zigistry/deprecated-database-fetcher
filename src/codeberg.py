import json
from typing import Dict, List
from dataclasses import asdict
import requests

from libs.types import Dependency, Repo
from libs.z2j import get_repo_zon_metadata
from libs.utils import (
    file_exists_on_repo,
    process_dependency_url,
    extract_repo_info,
)

def convert_codeberg_response_to_repo(codeberg_response: Dict) -> Repo:
    full_name = codeberg_response.get("full_name", "")
    zig_minimum_version = "unknown"
    dependencies: List[Dependency] = []

    base_url = "https://codeberg.org"

    # Check for build.zig and build.zig.zon (using session)
    has_build_zig = file_exists_on_repo(base_url, full_name, "build.zig", "codeberg")
    has_build_zig_zon = file_exists_on_repo(base_url, full_name, "build.zig.zon", "codeberg")

    if has_build_zig_zon:
        try:
            zon_metadata = get_repo_zon_metadata(full_name, platform="codeberg")
            zig_minimum_version = zon_metadata.get("zig_version", "unknown")
            dependencies = [
                process_dependency_url(dep, extract_repo_info)
                for dep in zon_metadata.get("dependencies", [])
            ]
        except Exception as e:
            print(f"Error processing build.zig.zon for {full_name}: {e}")

    return Repo(
        avatar_url=codeberg_response.get("owner", {}).get("avatar_url"),
        name=codeberg_response.get("name"),
        full_name=full_name,
        created_at=codeberg_response.get("created_at"),
        default_branch=codeberg_response.get("default_branch"),
        dependencies=dependencies,
        description=codeberg_response.get("description"),
        fork=codeberg_response.get("fork"),
        forks_count=codeberg_response.get("forks_count", 0),
        has_build_zig=has_build_zig,
        has_build_zig_zon=has_build_zig_zon,
        license=codeberg_response.get("license", "-"),
        open_issues=codeberg_response.get("open_issues_count", 0),
        readme_content="404",
        repo_from="codeberg",
        size=codeberg_response.get("size", 0),
        stargazers_count=codeberg_response.get("stars_count", 0),
        tags_url="",
        topics=codeberg_response.get("topics", []),
        updated_at=codeberg_response.get("updated_at"),
        watchers_count=codeberg_response.get("watchers_count", 0),
        zig_minimum_version=zig_minimum_version,
    )


def fetch_all_codeberg_repos(query: str, topic_required: bool = True) -> List[Dict]:
    all_results = []
    page = 1
    session = requests.Session()

    while True:
        url = f"https://codeberg.org/api/v1/repos/search?q={query}&page={page}"
        if topic_required:
            url += "&topic=true"

        res = session.get(url, timeout=10)
        if res.status_code != 200:
            print(f"Failed fetching page {page}, status {res.status_code}")
            break

        items = res.json().get("data", [])
        if not items:
            break

        all_results.extend(items)
        page += 1

    return all_results


def dedupe(repos: List[Dict]) -> List[Dict]:
    seen = set()
    out = []
    for r in repos:
        name = r["full_name"]
        if name not in seen:
            seen.add(name)
            out.append(r)
    return out


def write_json(path: str, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)



if __name__ == "__main__":
    session = requests.Session()

    print("Fetching zig-package repositories...")

    raw_repos = fetch_all_codeberg_repos(query="zig", topic_required=True)

    zig_package_repos = [
        r for r in raw_repos
        if "zig-package" in r.get("topics", [])
    ]

    converted = [
        convert_codeberg_response_to_repo(r)
        for r in zig_package_repos
    ]

    with open("./database/packages.json", "r") as f:
        existing_packages = json.load(f)

    final_packages = dedupe(existing_packages + [asdict(r) for r in converted])
    write_json("./database/packages.json", final_packages)

    print(f"Saved {len(final_packages)} zig-package repos -> packages.json")

    print("Fetching zig programs (general Zig repos)...")

    raw_programs = fetch_all_codeberg_repos(query="zig", topic_required=True)

    program_converted = [
        convert_codeberg_response_to_repo(r)
        for r in raw_programs
    ]

    with open("./database/programs.json", "r") as f:
        existing_programs = json.load(f)

    final_programs = dedupe(existing_programs + [asdict(r) for r in program_converted])
    write_json("./database/programs.json", final_programs)

    print(f"Saved {len(final_programs)} zig repos -> programs.json")
