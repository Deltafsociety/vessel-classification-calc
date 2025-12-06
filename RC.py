import streamlit as st

# --- 1. CONFIGURATION: DEFAULT & HIDDEN SETTINGS ---

# Base Fees by Gross Tonnage (GT) Band - Using the midpoint of your specified ranges for a single price.
BASE_FEE_RANGES = {
    (100, 299): 7000,    # Midpoint of $6,000 - $8,000
    (300, 499): 9000,    # Midpoint of $8,000 - $10,000
    (500, 2499): 14000,  # Midpoint of $10,000 - $18,000
    (2500, 100000): 25000, # Suggested price for '+2500' band
}

# Default Weights (Used if not modified in settings)
DEFAULT_WEIGHTS = {
    "Vessel Type": 0.40, 
    "Vessel Age (Years)": 0.30, 
    "Flag State Performance": 0.15,
    "PSC Deficiencies (3 yrs)": 0.15,
}

# Risk Factor Definitions (Scores)
RISK_FACTORS = {
    "Vessel Type": {
        "options": {
            "General Cargo/Container (Low)": 0,
            "Bulk Carrier/Offshore (Medium)": 1,
            "Oil/Chemical/Gas Tanker (High)": 3,
            "Passenger Ship (Highest)": 4,
        }
    },
    "Vessel Age (Years)": {
        "options": {
            "< 5 Years (New)": -1,
            "5 - 19 Years (Standard)": 0,
            "20 - 29 Years (Aging)": 2,
            "30+ Years (Very Old)": 3,
        }
    },
    "Flag State Performance": {
        "options": {
            "White List (Best)": -1,
            "Grey List (Standard)": 1,
            "Black List (Worst)": 3,
        }
    },
}

# Risk Score to Adjustment Percentage Mapping
ADJUSTMENT_MAPPING = {
    "Low Risk (Discount)": {"min_R": -5, "max_R": 0, "adjustment": -0.10}, 
    "Standard Risk (No Change)": {"min_R": 0, "max_R": 1.0, "adjustment": 0.0},
    "Elevated Risk (Surcharge)": {"min_R": 1.0, "max_R": 2.5, "adjustment": 0.15},
    "High Risk (Significant Surcharge)": {"min_R": 2.5, "max_R": 5, "adjustment": 0.30},
}

# --- 2. CALCULATION FUNCTIONS ---

def get_base_fee_for_gt(gt_input):
    """Determines the single base annual fee based on the entered GT number."""
    for (min_gt, max_gt), fee in BASE_FEE_RANGES.items():
        if min_gt <= gt_input <= max_gt:
            note = ""
            if min_gt == 2500:
                note = " (Suggested Midpoint)"
            return fee, f"{min_gt:,.0f} - {max_gt:,.0f} GT Band Midpoint{note}"
    
    if gt_input < 100:
        return BASE_FEE_RANGES[(100, 299)], "Below 100 GT (Using lowest defined band)"
    if gt_input > 100000:
        return BASE_FEE_RANGES[(2500, 100000)], "Over 100,000 GT (Using highest defined band)"
        
    return 0, "GT out of defined range"

def calculate_deficiency_score(deficiencies):
    """Assigns a score based on the number of deficiencies (over 3 years)."""
    if deficiencies == 0:
        return -2.0 # Rewards good performance
    elif 1 <= deficiencies <= 4:
        return 0.5 # Minor, slightly elevated risk
    elif 5 <= deficiencies <= 9:
        return 1.5 # Moderate risk
    else: # 10+ deficiencies
        return 3.5 # High risk
        
def calculate_risk_score(selected_factors, deficiencies_count, weights):
    """Calculates the weighted risk score including the dynamic deficiency score."""
    total_risk_score = 0
    
    # 1. Calculate score for fixed factors (Type, Age, Flag)
    for factor, selection in selected_factors.items():
        score = RISK_FACTORS[factor]['options'].get(selection, 0)
        weight = weights.get(factor, 0)
        total_risk_score += score * weight
        
    # 2. Calculate score for dynamic deficiency factor
    deficiency_score = calculate_deficiency_score(deficiencies_count)
    deficiency_weight = weights.get("PSC Deficiencies (3 yrs)", 0)
    total_risk_score += deficiency_score * deficiency_weight
        
    return total_risk_score

def get_adjustment_factor(risk_score):
    """Determines the risk adjustment factor."""
    for category, mapping in ADJUSTMENT_MAPPING.items():
        if mapping["min_R"] <= risk_score <= mapping["max_R"]:
            return mapping["adjustment"], category
    return 0.0, "Undefined Risk"

def calculate_charge(base_fee, adj_factor):
    """Applies the adjustment factor to the base fee."""
    return base_fee * (1 + adj_factor)

# --- 3. STREAMLIT APP LAYOUT ---

st.set_page_config(layout="wide", page_title="Vessel Classification Fee Estimator")

st.title("Vessel Classification Fee Estimator")
st.markdown("This tool provides a risk-adjusted estimate for the annual classification charge based on vessel Gross Tonnage (GT) and operational history.")

# Use session state to store weights
if 'weights' not in st.session_state:
    st.session_state.weights = DEFAULT_WEIGHTS

# --- Calculation Settings (Hidden by Default) ---
with st.expander("Calculation Settings: Adjust Base Fees and Risk Factor Weights"):
    st.markdown("### 1. GT Band Base Fees (Midpoint used for calculation)")
    
    new_fee_ranges = {}
    st.info("The base fees are calculated as the midpoint of the following ranges.")
    
    # Allow user to modify the midpoints for calculation
    i = 0
    cols = st.columns(len(BASE_FEE_RANGES))
    for (min_gt, max_gt), fee in BASE_FEE_RANGES.items():
        range_label = f"{min_gt:,.0f} - {max_gt:,.0f} GT"
        new_fee_ranges[(min_gt, max_gt)] = cols[i].number_input(
            f"Midpoint Fee for {range_label}", 
            value=fee, 
            min_value=0, 
            step=1000
        )
        i += 1
    BASE_FEE_RANGES.update(new_fee_ranges)
    
    st.markdown("### 2. Risk Factor Weights (%)")
    st.markdown("Adjust the influence of each factor. The total weight should ideally sum to **1.0 (100%)**.")

    col_w1, col_w2 = st.columns(2)
    new_weights = {}
    i = 0
    # Add 'PSC Deficiencies' to the factors list for weight adjustment
    weight_factors = list(RISK_FACTORS.keys()) + ["PSC Deficiencies (3 yrs)"]
    
    for factor in weight_factors:
        weight = st.session_state.weights.get(factor, 0.0)
        container = col_w1 if i % 2 == 0 else col_w2
        new_weights[factor] = container.slider(
            factor,
            min_value=0.0,
            max_value=1.0,
            value=weight,
            step=0.05,
            key=f"weight_slider_{factor}",
            help="Weight of this factor in the final risk score."
        )
        i += 1
    
    st.session_state.weights = new_weights
    st.metric("Current Total Weight", f"{sum(st.session_state.weights.values()):.2f}")

# --- Main Inputs ---

col1, col2 = st.columns(2)

# Input for specific GT number
gt_input = col1.number_input(
    "Enter Vessel Gross Tonnage (GT)",
    min_value=100,
    max_value=100000,
    value=5000,
    step=10
)

# Input for Deficiencies Count
deficiencies_input = col2.number_input(
    "Number of PSC Deficiencies (Last 3 years)",
    min_value=0,
    value=3,
    step=1,
    help="Enter the total count of deficiencies recorded during Port State Control inspections in the past 3 years."
)

# Determine the base fee for the GT input
base_fee, gt_band_source = get_base_fee_for_gt(gt_input)
st.metric("Calculated Base Annual Fee", f"${base_fee:,.0f}", help=f"Base Fee derived from the {gt_band_source}")

st.markdown("### Select Fixed Risk Attributes")
selected_factors = {}
risk_cols = st.columns(len(RISK_FACTORS))
i = 0
for factor, data in RISK_FACTORS.items():
    selected_factors[factor] = risk_cols[i].selectbox(
        f"**{factor}**",
        list(data['options'].keys())
    )
    i += 1

st.markdown("---") # Separator 

## Fee Estimate and Risk Summary

# Calculation
final_risk_score = calculate_risk_score(selected_factors, deficiencies_input, st.session_state.weights)
adj_factor, risk_category = get_adjustment_factor(final_risk_score)
final_charge = calculate_charge(base_fee, adj_factor)

# Pre-format the final charge
final_charge_formatted = f'{final_charge:,.0f}' 

col_res1, col_res2, col_res3 = st.columns(3)

col_res1.metric(
    "Final Risk Score",
    f"{final_risk_score:.2f}",
    help="Weighted sum of factor scores. Used to determine the fee adjustment."
)
col_res2.metric(
    "Risk Category",
    risk_category,
    delta=f"{adj_factor * 100:.0f}% Adjustment",
    delta_color="inverse" if adj_factor < 0 else "normal",
    help="The category maps the risk score to a fee adjustment percentage."
)
col_res3.metric(
    "Estimated Annual Charge",
    f"${final_charge_formatted}",
    help="Base Fee adjusted by the Risk Factor. This is a single, risk-weighted price estimate."
)

st.divider() 

st.markdown("### Detailed Calculation Summary")

st.markdown(f"""
The final charge is calculated by applying the **{adj_factor * 100:.0f}%** adjustment factor (based on the **{risk_category}** mapping) to the Base Annual Fee of **${base_fee:,.0f}**:

$$
\\text{{Final Charge}} = \\text{{Base Fee}} \\times (1 + \\text{{Adjustment Factor}})
$$
$$
\\text{{Final Charge}} = \${base_fee:,.0f} \\times (1 + {adj_factor:.2f}) = \$\mathbf{{{final_charge_formatted}}}
$$
""")