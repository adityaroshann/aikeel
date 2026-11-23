"""AIkeel demo UI.  Run:  streamlit run streamlit_app.py"""
from __future__ import annotations

import hashlib
import re
import time
from pathlib import Path

import pandas as pd
import streamlit as st

from keel.engine import run
from keel.infer import LOW_CONFIDENCE, infer_profile
from keel.llm import LLM
from keel.profile import CustomerProfile
from ui_render import render

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "customers"
PROFILES = ROOT / "profiles"

st.set_page_config(page_title="AIkeel: onboard any shipyard with config, not code", page_icon="⚓",
                   layout="wide")
DEMO_CUSTOMER = "hidden_c"  # the customer onboarded live at the booth


def customers() -> list[str]:
    return sorted(p.name for p in DATA.iterdir() if p.is_dir()) if DATA.exists() else []


def profile_path(c: str) -> Path:
    return PROFILES / f"{c}.yaml"


def engine_fingerprint() -> tuple[str, int, int]:
    h, lines, files = hashlib.sha256(), 0, 0
    for p in sorted((ROOT / "keel").rglob("*.py")):
        b = p.read_bytes()
        h.update(b)
        lines += b.count(b"\n")
        files += 1
    return h.hexdigest()[:12], files, lines


# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("Customer")
    names = customers()
    label = lambda c: f"{c}  {'✅ onboarded' if profile_path(c).exists() else '🆕 new'}"  # noqa: E731
    customer = st.radio("Choose a customer", names, format_func=label)

    with st.expander("Add a customer from files"):
        new_name = st.text_input("Customer id", placeholder="e.g. yard_d")
        ups = st.file_uploader("Equipment list (.csv/.xlsx), GA drawing (.dxf), standards (.md/.txt)",
                               accept_multiple_files=True)
        if st.button("Create customer", disabled=not (new_name and ups)):
            slug = re.sub(r"[^a-z0-9_]+", "_", new_name.lower()).strip("_")
            d = DATA / slug
            d.mkdir(parents=True, exist_ok=True)
            for u in ups:
                (d / Path(u.name).name).write_bytes(u.getvalue())
            st.success(f"Created {slug}")
            st.rerun()

    st.divider()
    st.header("Claude (optional)")
    key = st.text_input("Anthropic API key", type="password",
                        help="Not needed. Without a key everything runs offline on heuristics.")
    use_llm = st.toggle(f"Send low-confidence decisions (< {LOW_CONFIDENCE:.0%}) to Claude",
                        value=bool(key) or LLM.env_available(),
                        disabled=not (key or LLM.env_available()))
    st.divider()
    if st.button("↺ Reset demo", help=f"Forget the approved profile for `{DEMO_CUSTOMER}` so it can be "
                                      "onboarded live again."):
        profile_path(DEMO_CUSTOMER).unlink(missing_ok=True)
        for k in [k for k in st.session_state if k.endswith(f"_{DEMO_CUSTOMER}")]:
            del st.session_state[k]
        st.rerun()
    st.caption("⚓ **AIkeel**. Built for Genesis T-Minus30. Synthetic data only.")

st.title("⚓ AIkeel")
st.markdown("#### Onboard any shipyard in an afternoon, not a quarter")
st.caption("Every yard names, tags, layers and limits things differently. AIkeel proposes a reviewable "
           "**customer profile** from sample files, and the **same engine** runs QA/QC checks for every customer. "
           "The AI explains, the engineer decides.")

if not customer:
    st.info("Run `python scripts/make_sample_data.py` to create the sample customers.")
    st.stop()

cdir = DATA / customer
state_key = f"profile_{customer}"
if state_key not in st.session_state and profile_path(customer).exists():
    st.session_state[state_key] = CustomerProfile.load(profile_path(customer))
    st.session_state[f"props_{customer}"] = None

tab0, tab1, tab2, tab3 = st.tabs(["⓪ Why AIkeel", "① Onboard (propose → review → approve)",
                                  "② Run checks on the GA drawing", "③ Config, not code"])

# ---------------------------------------------------------------- tab 0
with tab0:
    p, s = st.columns(2)
    with p:
        st.subheader("The problem")
        st.markdown(
            "AI can check ship designs for mistakes before steel is cut, when fixing them is still cheap. "
            "The hard part isn't the AI. **Every shipyard keeps its data differently:**\n"
            "- Excel in tonnes vs CSV in pounds\n"
            "- `P-101` vs `721.01-PMP-02` vs `ER-PU-0007` for the same pump\n"
            "- Different CAD layers, and different places tags are stored\n"
            "- Their own internal standards and limits\n\n"
            "Today each new customer means **custom code**. Onboarding takes weeks, and the product splinters "
            "into one version per customer.")
    with s:
        st.subheader("What AIkeel does")
        st.markdown(
            "Drop in a new customer's sample files. In about a second AIkeel **proposes how that customer "
            "works**: column meanings, units, tag format, drawing layers and weight limits. Every guess comes "
            "with **evidence and a confidence score**.\n\n"
            "An engineer reviews it and clicks approve. From then on the **same checking engine** finds that "
            "customer's errors, **with zero new code**.\n\n"
            "> *The AI explains. The engineer decides.*")
    st.divider()
    steps = [("1 · Upload", "Equipment list, GA drawing (DXF), standards note"),
             ("2 · Propose", "AIkeel infers a customer profile, with evidence for each decision"),
             ("3 · Approve", "An engineer reviews and edits one YAML file"),
             ("4 · Check", "The same engine catches missing, duplicate, mis-tagged and overweight items")]
    for col, (head, body) in zip(st.columns(4), steps):
        col.markdown(f"**{head}**")
        col.caption(body)
    st.divider()
    w, h = st.columns(2)
    w.markdown("**Who it's for:** ship-design software vendors, naval-architecture and design offices, and "
               "yards doing defence and coast-guard work. Anyone who onboards customers whose data never "
               "looks the same twice.")
    h.markdown("**Runs on-prem / offline.** Heuristics handle the clear cases with no internet. Claude is "
               "optional and only sees the low-confidence decisions.")

# ---------------------------------------------------------------- tab 1
with tab1:
    files = sorted(p.name for p in cdir.iterdir() if p.is_file() and not p.name.startswith("_"))
    st.markdown(f"**Files received from `{customer}`:** " + ", ".join(f"`{f}`" for f in files))
    if profile_path(customer).exists():
        st.success(f"Approved profile on file: `profiles/{customer}.yaml`. Re-run the autopilot to compare.")

    if st.button("🚀 Run Onboarding Autopilot", type="primary"):
        llm = LLM(api_key=key or None) if use_llm else None
        t0 = time.perf_counter()
        with st.spinner("Reading the customer's files..."):
            prof, props = infer_profile(cdir, customer, llm=llm)
        st.session_state[state_key] = prof
        st.session_state[f"props_{customer}"] = props
        st.session_state[f"elapsed_{customer}"] = time.perf_counter() - t0
        if llm and llm.last_error:
            st.warning(f"Claude unavailable ({llm.last_error}); kept the heuristic proposals.")

    props = st.session_state.get(f"props_{customer}")
    prof = st.session_state.get(state_key)
    if props:
        low = [p for p in props if p.confidence < LOW_CONFIDENCE]
        c1, c2, c3 = st.columns(3)
        c1.metric("Decisions proposed", len(props))
        c2.metric("Need engineer attention", len(low))
        c3.metric("Time to propose", f"{st.session_state[f'elapsed_{customer}']:.2f} s")
        df = pd.DataFrame([{"Decision": p.field, "Proposed value": str(p.value), "Confidence": p.confidence,
                            "By": p.method, "Evidence (why)": p.evidence} for p in props])
        st.dataframe(df, hide_index=True, width="stretch", column_config={
            "Confidence": st.column_config.ProgressColumn(min_value=0, max_value=1, format="%.2f"),
            "Evidence (why)": st.column_config.TextColumn(width="large")})
    if prof:
        st.subheader("Customer profile (review and edit, then approve)")
        text = st.text_area("profile YAML", prof.to_yaml(), height=420, label_visibility="collapsed",
                            key=f"yaml_{customer}_{id(prof)}")
        if st.button("✅ Approve & save profile"):
            try:
                approved = CustomerProfile.from_yaml(text)
                approved.save(profile_path(customer))
                st.session_state[state_key] = approved
                st.success(f"Saved `profiles/{customer}.yaml`. No code was written.")
            except Exception as e:  # validation errors are shown to the engineer
                st.error(f"Profile is not valid: {e}")
    elif not props:
        st.info("New customer. Run the autopilot to propose a profile.")

# ---------------------------------------------------------------- tab 2
with tab2:
    prof = st.session_state.get(state_key)
    if not prof:
        st.info("Onboard this customer first (tab ①).")
    else:
        result = run(cdir, prof)
        errs = sum(f.severity == "error" for f in result.findings)
        warns = len(result.findings) - errs
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Equipment list items", len(result.equipment))
        c2.metric("Tags found on drawing", len(result.tags))
        c3.metric("Errors", errs)
        c4.metric("Warnings", warns)
        st.image(render(cdir / prof.drawing.file, result), width="stretch")
        st.dataframe(pd.DataFrame([{"Severity": f.severity, "Check": f.check, "Item / space": f.tag,
                                    "Finding": f.message, "Evidence": f.evidence} for f in result.findings]),
                     hide_index=True, width="stretch")

# ---------------------------------------------------------------- tab 3
with tab3:
    fp, nfiles, nlines = engine_fingerprint()
    onboarded = [c for c in names if profile_path(c).exists()]
    st.markdown(f"**Engine:** `{nfiles}` files, `{nlines}` lines, fingerprint `{fp}`. "
                f"It is the same for all **{len(onboarded)}** onboarded customers.")
    if len(onboarded) >= 2:
        a, b = st.columns(2)
        left = a.selectbox("Profile", onboarded, index=0)
        right = b.selectbox("Profile ", onboarded, index=1)
        for col, c in ((a, left), (b, right)):
            txt = profile_path(c).read_text(encoding="utf-8")
            col.caption(f"`profiles/{c}.yaml`: {txt.count(chr(10))} lines")
            col.code(txt, language="yaml")
        st.markdown("**Each new customer costs one reviewed YAML file. Code changed per customer: 0 lines.**")
    else:
        st.info("Approve at least two customer profiles to compare them side by side.")
