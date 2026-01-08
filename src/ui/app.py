"""
Streamlit UI for the Autonomous Grocery Shopping Super-Agent.
- Initial planning
- Cart review
- User feedback (modify / remove / recompare / questions)
- Checkout confirmation
"""

import streamlit as st
import requests
import uuid
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from models.grocery_list import ParsedGroceryList, ParsedGroceryItem
from core.db import get_db_connection
from agents.super_agent import execute_agent, build_super_agent_graph
from models.state import AgentState
from core.llm_engine import parse_grocery_list_llm

# -------------------------------------------------
# Page config
# -------------------------------------------------
st.set_page_config(
    page_title="Grocery Shopping Super-Agent",
    page_icon="🛒",
    layout="wide",
)

# -------------------------------------------------
# Session state
# -------------------------------------------------
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "agent_state" not in st.session_state:
    st.session_state.agent_state = None
    
if "agent_graph" not in st.session_state:
    st.session_state.agent_graph = build_super_agent_graph()
    
if "processing" not in st.session_state:
    st.session_state.processing = False

# -------------------------------------------------
# Header
# -------------------------------------------------
st.markdown(
    "<h1 style='color:#1f77b4'>🛒 Autonomous Grocery Shopping Super-Agent</h1>",
    unsafe_allow_html=True
)
st.caption(f"Session ID: `{st.session_state.session_id}`")

tab_shop, tab_analysis, tab_settings = st.tabs(
    ["🛍️ Shopping", "📊 Analysis", "⚙️ Settings"]
)

# =================================================
# SHOPPING TAB
# =================================================
with tab_shop:
    st.subheader("Enter your grocery list")

    user_input = st.text_area(
        "Example: 5kg basmati rice, 500g groundnut",
        height=100
    )
    
    run_agent = st.button("🚀 Find Best Prices", disabled=st.session_state.processing)
    if run_agent:
        if not user_input.strip():
            st.warning("Please enter items.")
            st.stop()

        # 🔒 PREVENT RE-RUN IF STATE ALREADY EXISTS
        if st.session_state.agent_state is not None:
            st.info("🛒 Cart already created. Modify or confirm below.")
            st.stop()

        st.session_state.processing = True

        with st.spinner("🤖 Finding best deals..."):
            parsed = parse_grocery_list_llm(user_input)
            if not parsed or "items" not in parsed:
                st.session_state.processing = False
                st.error("Failed to parse grocery list.")
                st.stop()

            items = []
            for i in parsed["items"]:
                items.append(
                    ParsedGroceryItem(
                        item_name=i["item_name"],
                        quantity=float(i.get("quantity", 1)),
                        unit=i.get("unit", "pieces")
                    )
                )

            grocery_list = ParsedGroceryList(
                items=items,
                original_input=user_input
            )
            state = execute_agent(
                grocery_list,
                st.session_state.session_id
            )

        st.session_state.agent_state = state
        st.session_state.processing = False
        st.success("Cart created successfully!")

    # ---------------- CART + FEEDBACK ----------------
    if st.session_state.agent_state:
        state = st.session_state.agent_state
        st.write("Debug: Agent state loaded")

        if state.current_cart.items:
            st.subheader("🛒 Your Cart")

            table = [{
                "Product": i.product_name,
                "Brand": i.brand,
                "Qty": f"{i.display_quantity}{i.display_unit}",
                "Vendor": i.vendor.upper(),
                "Price": f"₹{i.price:.2f}",
                "Reason": i.decision_reason[:60]
            } for i in state.current_cart.items]

            st.dataframe(table, width="stretch", hide_index=True)

            st.markdown(f"### 💰 Total: ₹{state.current_cart.total_price:.2f}")
            st.markdown("---")

            st.subheader("🧠 Modify / Ask / Confirm")

            st.info(
                "Examples:\n"
                "- remove groundnut\n"
                "- change basmati rice to 10kg\n"
                "- recompare rice\n"
                "- why bigbasket?\n"
                "- confirm"
            )

            feedback = st.text_input("Your instruction")

            col1, col2 = st.columns(2)

            # ---------- APPLY FEEDBACK ----------            
            with col1:
                if st.button("🔄 Apply Change", disabled=st.session_state.processing):
                    st.session_state.processing = True
                    st.info(f"🤖 Processing your request with feedback... {feedback}")

                    if not feedback.strip():
                        st.warning("Enter a request.")
                        st.session_state.processing = False
                        st.stop()

                    # 🔑 ALWAYS work on session agent_state
                    agent_state = st.session_state.agent_state

                    agent_state.user_input = feedback
                    agent_state.awaiting_user_input = False
                    agent_state.processing_feedback = False
                    
                    # st.info(f"State before invoking graph: {agent_state}")

                    # 🔥 INVOKE GRAPH WITH THE SAME OBJECT
                    result = st.session_state.agent_graph.invoke(agent_state)
                    # st.info(f"Result after invoking graph: {result}")
                    updated_state = AgentState(**result)
                    # st.info(f"Updated state: {updated_state}")
                    # 🔥 FORCE STREAMLIT REFRESH
                    st.session_state.agent_state = None
                    st.session_state.agent_state = updated_state
                    # st.info(f"State after re-assigning: {st.session_state.agent_state}")
                    # 🔥 USE updated_state, NOT agent_state
                    table = [{
                        "Product": i.product_name,
                        "Brand": i.brand,
                        "Qty": f"{i.display_quantity}{i.display_unit}",
                        "Vendor": i.vendor.upper(),
                        "Price": f"₹{i.price:.2f}",
                        "Reason": i.decision_reason[:60]
                    } for i in updated_state.current_cart.items]

                    st.dataframe(table, width="stretch", hide_index=True)

                    st.markdown(f"### 💰 Total: ₹{updated_state.current_cart.total_price:.2f}")
                    st.markdown("---")

                    st.session_state.processing = False
                    st.success("Change applied!")
                    # st.rerun()
            # ---------- CONFIRM ----------                    
            with col2:
                if st.button("✅ Confirm & Checkout", disabled=st.session_state.processing):
                    st.info("🤖 Confirming order...")
                    st.session_state.processing = True

                    agent_state = st.session_state.agent_state
                    agent_state.user_input = "confirm"
                    agent_state.awaiting_user_input = True
                    agent_state.processing_feedback = False

                    result = st.session_state.agent_graph.invoke(agent_state)
                    updated_state = AgentState(**result)

                    # force Streamlit refresh
                    st.session_state.agent_state = None
                    st.session_state.agent_state = updated_state

                    st.session_state.processing = False
                    st.success("✅ Order confirmed successfully!")
                    st.rerun()


# =================================================
# ANALYSIS TAB (UNCHANGED)
# =================================================
with tab_analysis:
    if st.session_state.agent_state:
        state = st.session_state.agent_state

        st.subheader("Execution Plan")
        st.dataframe(
            [{
                "Step": s.step_id,
                "Action": s.action,
                "Status": s.status
            } for s in state.execution_plan.steps],
            width="stretch",
            hide_index=True
        )

        st.subheader("Decisions")
        for d in state.decisions_made:
            st.json(d)
    else:
        st.info("Run the agent to see analysis.")

# =================================================
# SETTINGS TAB (UNCHANGED)
# =================================================
with tab_settings:
    st.subheader("System Health")

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM products")
        count = cur.fetchone()[0]
        cur.execute("SELECT DISTINCT vendor FROM products")
        vendors = [r[0] for r in cur.fetchall()]
        conn.close()

        st.success("Database connected")
        st.write("Products:", count)
        st.write("Vendors:", ", ".join(vendors))
    except Exception as e:
        st.error(str(e))

    try:
        r = requests.get("http://localhost:8000/health", timeout=2)
        if r.status_code == 200:
            st.success("FastAPI running")
        else:
            st.error("FastAPI unhealthy")
    except Exception:
        st.error("FastAPI not reachable")

    if st.button("🔄 Reset Session"):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.agent_state = None
        st.success("Session reset")
        st.rerun()
