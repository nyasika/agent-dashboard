import streamlit as st
import anthropic
import yaml
from pathlib import Path

st.set_page_config(
    page_title="AI Agent Dashboard",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
    .agent-card { border: 1px solid #e0e0e0; border-radius: 10px; padding: 1rem; margin-bottom: 1rem; }
    .stButton button { width: 100%; }
</style>
""", unsafe_allow_html=True)


def load_agents(category: str) -> list[dict]:
    agents = []
    base = Path(f"agents/{category}")
    if not base.exists():
        return agents
    for agent_dir in sorted(base.iterdir()):
        config_file = agent_dir / "config.yaml"
        if config_file.exists():
            config = yaml.safe_load(config_file.read_text(encoding="utf-8"))
            config["id"] = f"{category}/{agent_dir.name}"
            agents.append(config)
    return agents


def get_client() -> anthropic.Anthropic:
    try:
        api_key = st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        st.error("Hiányzó API kulcs. Hozd létre a `.streamlit/secrets.toml` fájlt és add meg az `ANTHROPIC_API_KEY` értékét.")
        st.stop()
    return anthropic.Anthropic(api_key=api_key)


# Session state init
for key, default in [("active_agent", None), ("messages", [])]:
    if key not in st.session_state:
        st.session_state[key] = default


# ── Chat view ──────────────────────────────────────────────────────────────────
if st.session_state.active_agent:
    agent = st.session_state.active_agent

    col_back, col_title = st.columns([1, 8])
    with col_back:
        if st.button("← Vissza"):
            st.session_state.active_agent = None
            st.session_state.messages = []
            st.rerun()
    with col_title:
        st.title(f"{agent.get('icon', '🤖')}  {agent['name']}")
        st.caption(agent.get("description", ""))

    st.divider()

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if user_input := st.chat_input("Írj üzenetet..."):
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        client = get_client()
        full_response = ""

        with st.chat_message("assistant"):
            placeholder = st.empty()
            with client.messages.stream(
                model=agent.get("model", "claude-sonnet-4-6"),
                max_tokens=agent.get("max_tokens", 4096),
                system=agent.get("system_prompt", ""),
                messages=[
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state.messages
                ],
            ) as stream:
                for chunk in stream.text_stream:
                    full_response += chunk
                    placeholder.markdown(full_response + "▌")
            placeholder.markdown(full_response)

        st.session_state.messages.append({"role": "assistant", "content": full_response})

# ── Dashboard view ─────────────────────────────────────────────────────────────
else:
    st.title("🤖 AI Agent Dashboard")
    st.caption("Válassz egy agentet az indításhoz")
    st.divider()

    tab_personal, tab_axetris = st.tabs(["👤 Personal", "🏢 Axetris"])

    for tab, category in [(tab_personal, "Personal"), (tab_axetris, "Axetris")]:
        with tab:
            agents = load_agents(category)
            if not agents:
                st.info("Még nincs agent ebben a kategóriában. Hozz létre egy `config.yaml` fájlt az agent mappájában.")
                continue

            cols = st.columns(3)
            for i, agent in enumerate(agents):
                with cols[i % 3]:
                    with st.container(border=True):
                        st.subheader(f"{agent.get('icon', '🤖')} {agent['name']}")
                        st.caption(agent.get("description", ""))
                        if agent.get("tags"):
                            st.markdown(" ".join(f"`{t}`" for t in agent["tags"]))
                        st.write("")
                        if agent.get("url"):
                            st.link_button("↗ Megnyitás", agent["url"], use_container_width=True)
                        elif st.button("▶ Indítás", key=f"launch_{agent['id']}"):
                            st.session_state.active_agent = agent
                            st.session_state.messages = []
                            st.rerun()
