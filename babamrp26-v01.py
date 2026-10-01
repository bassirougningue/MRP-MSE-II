import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

# Configuration de la page haut de gamme
st.set_page_config(
    page_title="ROCHCorr 2026 | Système MRP II & BI",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- BASE DE DONNÉES TECHNIQUE ---
FACTEURS_ONDULATION = {"A": 1.50, "C": 1.43, "B": 1.32, "E": 1.25}

def decomposer_composition(chaine_comp, flute_type):
    """Analyse la chaîne et calcule le grammage exact avec le coefficient d'ondulation"""
    try:
        papiers = chaine_comp.split('-')
        grammages = [int(''.join(filter(str.isdigit, p))) for p in papiers]
        coeff = FACTEURS_ONDULATION.get(flute_type.upper(), 1.35)
        
        if len(grammages) == 3: # Single Wall
            g_tot = grammages[0] + (grammages[1] * coeff) + grammages[2]
            return round(g_tot), grammages, ["Liner Ext", "Cannelure", "Liner Int"]
        elif len(grammages) == 5: # Double Wall
            g_tot = grammages[0] + (grammages[1] * coeff) + grammages[2] + (grammages[3] * coeff) + grammages[4]
            return round(g_tot), grammages, ["Liner Ext", "Cannelure 1", "Liner Inter", "Cannelure 2", "Liner Int"]
        else:
            return round(sum(grammages) * 1.15), grammages, [f"Couche {i+1}" for i in range(len(grammages))]
    except:
        return 450, [140, 140, 140], ["Liner Ext", "Cannelure", "Liner Int"]

# --- TITRE PRINCIPAL ---
st.title("🏭 CorruPlan Enterprise Edition")
st.caption("Système MRP II unifié — Planification Technique, Logistique et Business Intelligence")

# --- BARRE LATÉRALE : PARAMÈTRES ET UX ---
st.sidebar.header("🕹️ Centre de Contrôle")

# L'interrupteur magique demandé par l'utilisateur
afficher_finance = st.sidebar.toggle("💰 Activer la vue financière", value=True)

if afficher_finance:
    st.sidebar.markdown("---")
    st.sidebar.subheader("Finances & Tarification")
    cout_tonne = st.sidebar.number_input("Coût Moyen Papier / Tonne (€)", value=850, step=50)
    prix_m2 = st.sidebar.number_input("Prix de Vente Moyen m² Fini (€)", value=1.20, step=0.1)

st.sidebar.markdown("---")
st.sidebar.subheader("Configuration Logistique")
moq_global = st.sidebar.number_input("Minimum de Commande (MOQ en T)", value=2.5, step=0.5)
poids_bobine_std = st.sidebar.number_input("Poids standard d'une bobine (T)", value=1.2, step=0.1)

with st.sidebar.expander("⏱️ Délais d'Approvisionnement (Jours)"):
    lt_kraft = st.sidebar.slider("Papiers Kraftliner (KL, SC)", 1, 7, 3)
    lt_recycled = st.sidebar.slider("Papiers Recyclés (TL, HP)", 1, 5, 1)

with st.sidebar.expander("🚨 Simulation d'Aléas Logistiques"):
    retard_fournisseur = st.sidebar.checkbox("Retard de livraison général (+24h)")
    laize_bloquee = st.sidebar.selectbox("Laize en rupture simulée", ["Aucune", "2200 mm", "2500 mm"])

# --- SOURCE DE DONNÉES ---
df_production_brute = pd.DataFrame({
    "Ref. Qualité": ["201A", "201A", "302C", "401BC", "302C"],
    "Cannelure": ["A", "A", "C", "B", "C"],
    "Composition": ["TL140-HP140-TL140", "TL140-HP140-TL140", "KL175-SC150-TL150", "KL200-HP150-TL150-SC150-TL175", "KL175-SC150-TL150"],
    "Laize (mm)": [2500, 2500, 2200, 2500, 2360],
    "Largeur À Plat (mm)": [2500, 2500, 2200, 2500, 2360],
    "Période": ["J+1", "J+2", "J+1", "J+1", "J+3"],
    "Besoin Brut (m²)": [1500, 2400, 1800, 2000, 1980],
    "Stock Initial (m²)": [100, 75, 56, 61, 56],
    "Tolérance (%)": [5, 5, 5, 8, 5]
})

# --- MOTEUR DE CALCUL UNIFIÉ ---
mrp_results = []
dispatch_rows = []
stocks_volatiles = df_production_brute.groupby("Ref. Qualité")["Stock Initial (m²)"].first().to_dict()

df_production_brute = df_production_brute.sort_values(by=["Ref. Qualité", "Période"]).reset_index(drop=True)

for idx, row in df_production_brute.iterrows():
    ref = row["Ref. Qualité"]
    brut = row["Besoin Brut (m²)"]
    cannelure = row["Cannelure"]
    comp_str = row["Composition"]
    laize = row["Laize (mm)"]
    w_box = row["Largeur À Plat (mm)"]
    periode = row["Période"]
    tolerance = row["Tolérance (%)"]
    
    # MRP Core
    stock_disp = stocks_volatiles.get(ref, 0)
    if stock_disp >= brut:
        net = 0
        stocks_volatiles[ref] = stock_disp - brut
    else:
        net = brut - stock_disp
        stocks_volatiles[ref] = 0
        
    grammage_total, list_g, list_roles = decomposer_composition(comp_str, cannelure)
    poids_total_t = (net * grammage_total) / 1000000
    
    # Trim Loss
    nb_poses = int(laize // w_box)
    largeur_utile = nb_poses * w_box
    chute_laize_mm = laize - largeur_utile if net > 0 else 0
    pct_chute = (chute_laize_mm / laize) * 100 if net > 0 else 0
    poids_chute_t = poids_total_t * (pct_chute / 100)
    
    # Finance (Calculé en arrière-plan quoi qu'il arrive)
    cout_mat = poids_total_t * (cout_tonne if afficher_finance else 0)
    perte_chute = poids_chute_t * (cout_tonne if afficher_finance else 0)
    ca_est = net * (prix_m2 if afficher_finance else 0)
    marge = ca_est - cout_mat

    mrp_results.append({
        "Période": periode, "Ref. Qualité": ref, "Composition": comp_str, "Grammage (g/m²)": grammage_total,
        "Laize (mm)": laize, "Besoin Brut (m²)": brut, "Stock Projeté (m²)": stocks_volatiles[ref],
        "Besoin Net (m²)": net, "Poids Requis (T)": round(poids_total_t, 3), "Poses": nb_poses,
        "Chute (mm)": chute_laize_mm, "% Chute": round(pct_chute, 2), "Poids Chute (T)": round(poids_chute_t, 3),
        "Coût Matière (€)": round(cout_mat, 2), "Perte Chute (€)": round(perte_chute, 2), "CA Estimé (€)": round(ca_est, 2), "Marge Brute (€)": round(marge, 2), "Tolérance": f"±{tolerance}%"
    })
    
    # Explosion BOM pour achat
    if net > 0:
        papiers = comp_str.split('-')
        for i, p in enumerate(papiers):
            type_papier = ''.join(filter(str.isalpha, p))
            g_couche = list_g[i]
            role = list_roles[i]
            coeff_couche = FACTEURS_ONDULATION.get(cannelure, 1.4) if "Cannelure" in role else 1.0
            poids_couche_t = (net * g_couche * coeff_couche) / 1000000
            
            lt = lt_kraft if type_papier in ["KL", "SC"] else lt_recycled
            p_num = int(periode.replace("J+", ""))
            date_cmd = f"J+{p_num - lt}" if (p_num - lt) >= 0 else "Déjà lancé (J-X)"
            
            dispatch_rows.append({
                "Période Production": periode, "Date Commande": date_cmd, "Ref. Qualité": ref,
                "Laize (mm)": laize, "Type Papier": type_papier, "Rôle Couche": role, "Poids (T)": poids_couche_t
            })

df_mrp_final = pd.DataFrame(mrp_results)
df_dispatch_final = pd.DataFrame(dispatch_rows)

# --- AFFICHAGE DES TOP KPIS ---
tot_brut = df_mrp_final["Besoin Brut (m²)"].sum()
tot_net = df_mrp_final["Besoin Net (m²)"].sum()
tot_tonnes = df_mrp_final["Poids Requis (T)"].sum()
tot_bobines = int(np.ceil(tot_tonnes / poids_bobine_std))

# Dynamisation du nombre de colonnes de KPI
kpi_cols = st.columns(6 if afficher_finance else 4)
kpi_cols[0].metric("Volume Brut Total", f"{tot_brut:,} m²")
kpi_cols[1].metric("Volume Net Global", f"{tot_net:,} m²")
kpi_cols[2].metric("Tonnage Papier", f"{tot_tonnes:.2f} T")
kpi_cols[3].metric("Total Bobines", f"{tot_bobines}")

if afficher_finance:
    ca_total = df_mrp_final["CA Estimé (€)"].sum()
    marge_globale = df_mrp_final["Marge Brute (€)"].sum()
    kpi_cols[4].metric("Chiffre d'Affaires", f"{ca_total:,.0f} €")
    kpi_cols[5].metric("Marge Brute", f"{marge_globale:,.0f} €", f"{(marge_globale/ca_total*100):.1f}%")

# --- STRUCTURE DES ONGLETS DE PRODUCTION ---
tab1, tab2, tab3, tab4 = st.tabs([
    "📋 Plan Directeur & MRP", "📐 Analyse des Laizes & Trim Loss", "🚛 Logistique & Réceptions", "🚨 Risques & Stress-Test"
])

# ONGLET 1 : PLAN GENERAL
with tab1:
    st.subheader("Calculateur Industriel des Besoins Nets")
    # Choix dynamique des colonnes selon affichage financier
    cols_to_show = ["Période", "Ref. Qualité", "Composition", "Grammage (g/m²)", "Besoin Brut (m²)", "Stock Projeté (m²)", "Besoin Net (m²)", "Poids Requis (T)", "Tolérance"]
    if afficher_finance:
        cols_to_show += ["CA Estimé (€)", "Marge Brute (€)"]
    
    st.dataframe(df_mrp_final[cols_to_show], use_container_width=True, hide_index=True)
    
    if afficher_finance:
        st.markdown("### Évolution de la Marge par Période de Production")
        fig_marge = px.bar(df_mrp_final, x="Période", y="Marge Brute (€)", color="Ref. Qualité", title="Marge Brute Générée par Jour (€)")
        st.plotly_chart(fig_marge, use_container_width=True)

# ONGLET 2 : OPTIMISATION LAIZES (TRIM LOSS)
with tab2:
    col_t1, col_t2 = st.columns([2, 1])
    with col_t1:
        st.subheader("Rapport d'Efficacité Géométrique de l'Ondulatrice (Trim Loss)")
        trim_cols = ["Période", "Ref. Qualité", "Laize (mm)", "Poses", "Chute (mm)", "% Chute", "Poids Chute (T)"]
        if afficher_finance:
            trim_cols += ["Perte Chute (€)"]
        st.dataframe(df_mrp_final[trim_cols], use_container_width=True, hide_index=True)
    
    with col_t2:
        st.subheader("Statistiques des Pertes")
        taux_gache = (df_mrp_final["Poids Chute (T)"].sum() / tot_tonnes) * 100
        st.metric("Taux de Gâche Linéaire Moyen", f"{taux_gache:.2f} %")
        if afficher_finance:
            st.metric("Coût Total de la Gâche Matière", f"{df_mrp_final['Perte Chute (€)'].sum():,.2f} €")

    # Si finance activée, afficher la cascade d'optimisation
    if afficher_finance:
        st.markdown("---")
        st.subheader("Analyse d'Impact Financier de la Gâche de Laize")
        perte_tot = df_mrp_final['Perte Chute (€)'].sum()
        cout_util = df_mrp_final['Coût Matière (€)'].sum() - perte_tot
        
        fig_water = go.Figure(go.Waterfall(
            orientation = "v", measure = ["relative", "relative", "relative", "total"],))
