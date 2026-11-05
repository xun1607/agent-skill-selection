from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from skill_selection.console.registry import load_registry, read_skill  # noqa: E402


@st.cache_data
def registry_data(lock_mtime: float) -> dict:
    return load_registry(ROOT)


def source_name(source_id: str) -> str:
    return source_id.replace("-", " ").title()


def source_file_url(skill: dict) -> str:
    source = skill["source"]
    return f"{source['repo_url']}/blob/{source['commit']}/{source['path']}"


st.caption("Inventory and provenance for locally pinned skill packages. Read-only; integrity is not evidence of utility.")

try:
    lock = ROOT / "config/registry/sources.lock.json"
    registry = registry_data(lock.stat().st_mtime)
except (OSError, ValueError) as error:
    st.error(f"Cannot load the local registry: {error}", icon=":material/error:")
    st.stop()

sources, skills = registry["sources"], registry["skills"]
ready = sum(skill["validation_status"] == "valid" for skill in skills)

with st.container(horizontal=True):
    st.metric("Pinned sources", len(sources), border=True)
    st.metric("Imported packages", len(skills), border=True)
    st.metric("Selection-ready", ready, border=True, help="Packages whose validation status is `valid`.")

st.header("Sources", icon=":material/source:")
source_columns = st.columns(max(1, len(sources)), gap="medium")
for column, source in zip(source_columns, sources):
    with column.container(border=True, height="stretch"):
        st.subheader(source_name(source["source_id"]))
        with st.container(horizontal=True):
            st.badge(f"{source['profiles']} packages", color="blue")
            color = "green" if source["valid_for_selection"] else "orange"
            st.badge(f"{source['valid_for_selection']} approved", color=color)
        st.caption(f"Pinned commit `{source['commit'][:12]}` · inventory {'available' if source['inventory_exists'] else 'missing'}")
        with st.container(horizontal=True):
            st.link_button("Repository", source["repo_url"], icon=":material/open_in_new:")
            st.link_button("Pinned commit", f"{source['repo_url']}/tree/{source['commit']}", icon=":material/commit:")

st.header("Skill catalog", icon=":material/library_books:")
with st.container(border=True):
    with st.form("registry_filters", border=False):
        search_col, status_col, source_col, action_col = st.columns([3, 2, 2, 1], vertical_alignment="bottom")
        with search_col:
            query = st.text_input(
                "Search",
                value=st.session_state.get("registry_query", ""),
                placeholder="Name, ID, or description",
            )
        with status_col:
            statuses = ["All"] + sorted({skill["validation_status"] for skill in skills})
            status = st.selectbox("Validation status", statuses)
        with source_col:
            source_options = ["All"] + [source["source_id"] for source in sources]
            source_filter = st.selectbox("Source", source_options, format_func=lambda value: value if value == "All" else source_name(value))
        with action_col:
            submitted = st.form_submit_button("Apply", icon=":material/filter_list:", width="stretch")
    if submitted:
        st.session_state.registry_query = query

    normalized = query.strip().lower()
    shown = [
        skill for skill in skills
        if (status == "All" or skill["validation_status"] == status)
        and (source_filter == "All" or skill["skill_id"].startswith(source_filter + "/"))
        and (not normalized or normalized in f"{skill['skill_id']} {skill['description']}".lower())
    ]
    st.caption(f"Showing {len(shown)} of {len(skills)} packages. Select one row to inspect it.")
    table = pd.DataFrame([{
        "Skill": skill["name"],
        "Source": source_name(skill["skill_id"].split("/", 1)[0]),
        "Status": skill["validation_status"],
        "Files": len(skill["resources"]),
        "Revision": skill["revision_id"].split(":")[-1][:12],
    } for skill in shown])
    selection = st.dataframe(
        table,
        hide_index=True,
        width="stretch",
        height=380,
        on_select="rerun",
        selection_mode="single-row",
        key="registry_catalog",
        column_config={
            "Files": st.column_config.NumberColumn(format="%d"),
            "Status": st.column_config.TextColumn(pinned=True),
        },
        alt="Filtered local skill package catalog",
    )

rows = selection.selection.rows
if rows and rows[0] < len(shown):
    st.session_state.registry_selected_id = shown[rows[0]]["skill_id"]
selected = next((skill for skill in shown if skill["skill_id"] == st.session_state.get("registry_selected_id")), None)

st.header("Package details", icon=":material/package_2:")
if selected is None:
    st.info("Select a row in the catalog to inspect its instructions, resources, and provenance.", icon=":material/touch_app:")
    st.stop()

with st.container(border=True):
    st.subheader(selected["name"])
    with st.container(horizontal=True):
        status_color = "green" if selected["validation_status"] == "valid" else "orange"
        st.badge(selected["validation_status"], color=status_color)
        st.badge(f"{len(selected['resources'])} resources", color="blue")
    st.write(selected["description"])
    with st.container(horizontal=True):
        st.link_button("Source file", source_file_url(selected), icon=":material/open_in_new:")
        st.link_button("Repository", selected["source"]["repo_url"], icon=":material/code:")
        st.link_button(
            "Pinned commit",
            f"{selected['source']['repo_url']}/tree/{selected['source']['commit']}",
            icon=":material/commit:",
        )
    if selected["validation_issues"]:
        with st.container(horizontal=True):
            for issue in selected["validation_issues"]:
                st.badge(issue, color="orange")

    instructions, resources, provenance = st.tabs(["Instructions", "Resources", "Provenance"])
    with instructions:
        try:
            with st.container(height=520):
                st.markdown(read_skill(ROOT, selected))
        except OSError as error:
            st.error(f"Package content is unavailable: {error}")
    with resources:
        st.dataframe(
            selected["resources"],
            hide_index=True,
            width="stretch",
            column_config={
                "path": st.column_config.TextColumn("File", pinned=True),
                "size_bytes": st.column_config.NumberColumn("Size", format="localized"),
                "sha256": st.column_config.TextColumn("SHA-256"),
            },
            alt=f"Resources bundled with {selected['name']}",
        )
    with provenance:
        st.table({
            ":material/fingerprint: Skill ID": selected["skill_id"],
            ":material/source: Source path": selected["source"]["path"],
            ":material/commit: Source commit": selected["source"]["commit"],
            ":material/package_2: Package": selected["package_ref"],
        }, border="horizontal", width="stretch")
        with st.expander("Technical identifiers", icon=":material/key:"):
            st.code(selected["revision_id"], language=None)
