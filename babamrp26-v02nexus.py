import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO

# Configuration de la page haut de gamme
st.set_page_config(
    page_title="CorruPlan Nexus Enterprise",
    page_icon="🏭",
    layout="wide"
)

# --- CONSTANTES TECHNIQUES ET FINANCIÈRES ---
FACTEURS_ONDULATION = {"A": 1.50, "C": 1.43, "B": 1.32, "E": 1.25}

# Ratio de consommation de colle (amidon liquide) en g/m² de surface ondulée développée
CONSOMMATION_COLLE_BASE = {"A": 3.5, "C": 4.0, "B": 4.8, "E": 5.5} 

def decomposer_composition_dynamique(chaine_comp, combo_cannelure):
    """Analyse dynamique de l'empilement (3, 5 ou 7 couches)"""
    try:
        papiers = chaine_comp.split('-')
        grammages = [int(''.join(filter(str.isdigit, p))) for p in papiers]
        cannelures_list = list(combo_cannelure.upper())
        
        roles = []
        grammages_reels = []
        colle_m2_total = 0 # g/m²
        cannelure_index = 0
        
        for i in range(len(grammages)):
            if i % 2 == 0:
                if i == 0: roles.append("Liner Extérieur")
                elif i == len(grammages) - 1: roles.append("Liner Intérieur")
                else: roles.append(f"Médium Intermédiaire {i//2}")
                grammages_reels.append(grammages[i])
            else:
                flute_active = cannelures_list[cannelure_index] if cannelure_index < len(cannelures_list) else "C"
                roles.append(f"Cannelure {flute_active} ({cannelure_index + 1})")
                coeff = FACTEURS_ONDULATION.get(flute_active, 1.35)
                grammages_reels.append(round(grammages[i] * coeff))
                
                colle_m2_total += CONSOMMATION_COLLE_BASE.get(flute_active, 4.0) * coeff * 2
                cannelure_index += 1
                
        return sum(grammages_reels), grammages_reels, roles, round(colle_m2_total, 1)
    except:
        return 450, [140, 140, 140], ["Liner Ext", "Cannelure", "Liner Int"], 8.0

# --- INTERFACE PRINCIPALE ---
st.title("🏭 ROCH Nexus Enterprise")
st.caption("Système unifié MRP II, MES & Business Intelligence pour Usines d'Ondulation")

# --- BARRE LATÉRALE : PILOTAGE GLOBAL ---
st.sidebar.header("🕹️ Centre de Pilotage")
afficher_finance = st.sidebar.toggle("💰 Activer la vue financière", value=True)

if afficher_finance:
    st.sidebar.markdown("---")
    st.sidebar.subheader("Données Budgétaires")
    cout_tonne = st.sidebar.number_input("Coût Moyen Papier / Tonne (€)", value=880, step=50)
    prix_m2 = st.sidebar.number_input("Prix de Vente Moyen m² Fini (€)", value=1.45, step=0.1)
    cout_colle_kg = st.sidebar.number_input("Coût de l'Amidon sec (€/kg)", value=0.45, step=0.05)

st.sidebar.markdown("---")
st.sidebar.subheader("Contraintes d'Atelier")
moq_global = st.sidebar.number_input("Minimum de Commande Papier (T)", value=2.5, step=0.5)
poids_bobine_std = st.sidebar.number_input("Poids standard d'une bobine (T)", value=1.5, step=0.1)

# SOURCE DE DONNÉES
st.sidebar.markdown("---")
st.sidebar.subheader("📂 Source des Données")
mode_import = st.sidebar.radio("Sélectionner la source :", ["Plan de Démo (Avec Triplex)", "Uploader un fichier (Excel/CSV)"])

df_source = pd.DataFrame()

if mode_import == "Plan de Démo (Avec Triplex)":
    df_source = pd.DataFrame({
        "Ref. Qualité": ["201A", "302C", "401BC", "501BCE", "302C"],
        "Cannelure": ["A", "C", "BC", "BCE", "C"],
        "Composition": [
            "TL140-HP140-TL140", 
            "KL175-SC150-TL150", 
            "KL200-HP150-TL150-SC150-TL175", 
            "KL250-HP160-TL150-SC160-TL150-HP160-TL200", 
            "KL175-SC150-TL150"
        ],
        "Laize (mm)": [2200, 2200, 2200, 2500, 2360],
        "Largeur À Plat (mm)": [2200, 2200, 2200, 2500, 2360],
        "Période": ["J+1", "J+1", "J+1", "J+2", "J+3"],
        "Besoin Brut (m²)":[1500, 2000, 8000, 3000, 4500],
        "Stock Initial (m²)": [200, 100, 90, 250, 360],
        "Tolérance (%)": [5, 5, 8, 10, 5]
    })
else:
    fichier_charge = st.sidebar.file_uploader("Glissez votre planning de production ici", type=["xlsx", "csv"])
    if fichier_charge is not None:
        try:
            if fichier_charge.name.endswith(".csv"):
                df_source = pd.read_csv(fichier_charge)
            else:
                df_source = pd.read_excel(fichier_charge)
            st.sidebar.success("✅ Fichier importé avec succès !")
        except Exception as e:
            st.sidebar.error(f"Erreur lors de la lecture du fichier : {e}")

# --- TRAITEMENT DU MOTEUR DE CALCULS ---
if not df_source.empty:
    mrp_results = []
    dispatch_rows = []
    stocks_volatiles = df_source.groupby("Ref. Qualité")["Stock Initial (m²)"].first().to_dict()
    
    for idx, row in df_source.sort_values(by=["Période"]).iterrows():
        ref = row["Ref. Qualité"]
        brut = row["Besoin Brut (m²)"]
        cannelure = row["Cannelure"]
        comp_str = row["Composition"]
        laize = row["Laize (mm)"]
        w_box = row["Largeur À Plat (mm)"]
        periode = row["Période"]
        tolerance = row["Tolérance (%)"]
        
        # MRP Netting
        stock_disp = stocks_volatiles.get(ref, 0)
        net = max(0, brut - stock_disp)
        stocks_volatiles[ref] = max(0, stock_disp - brut)
        
        # Structure, Grammage et Colle
        grammage_total, list_g_reels, list_roles, colle_g_m2 = decomposer_composition_dynamique(comp_str, cannelure)
        poids_total_t = (net * grammage_total) / 1000000
        poids_colle_kg = (net * colle_g_m2) / 1000
        
        # Trim Loss
        nb_poses = int(laize // w_box)
        largeur_utile = nb_poses * w_box
        chute_laize_mm = laize - largeur_utile if net > 0 else 0
        pct_chute = (chute_laize_mm / laize) * 100 if net > 0 else 0
        poids_chute_t = poids_total_t * (pct_chute / 100)
        
        # Finances
        cout_mat = poids_total_t * (cout_tonne if afficher_finance else 0)
        cout_colle = poids_colle_kg * (cout_colle_kg if afficher_finance else 0)
        perte_chute = poids_chute_t * (cout_tonne if afficher_finance else 0)
        ca_est = net * (prix_m2 if afficher_finance else 0)
        marge = ca_est - cout_mat - cout_colle

        mrp_results.append({
            "Période": periode, "Ref. Qualité": ref, "Composition": comp_str, "Grammage (g/m²)": grammage_total, "Laize (mm)": laize,
            "Besoin Brut (m²)": brut, "Stock Projeté (m²)": stocks_volatiles[ref], "Besoin Net (m²)": net, "Poids Requis (T)": round(poids_total_t, 3),
            "Poses": nb_poses, "Chute (mm)": chute_laize_mm, "% Chute": round(pct_chute, 2), "Poids Chute (T)": round(poids_chute_t, 3),
            "Consommation Colle (kg)": round(poids_colle_kg, 1), "Coût Matière (€)": round(cout_mat, 2), "Coût Colle (€)": round(cout_colle, 2),
            "Perte Chute (€)": round(perte_chute, 2), "CA Estimé (€)": round(ca_est, 2), "Marge Brute (€)": round(marge, 2), "Tolérance": f"±{tolerance}%"
        })
        
        # Explosion BOM
        if net > 0:
            papiers = comp_str.split('-')
            for i, p in enumerate(papiers):
                type_papier = ''.join(filter(str.isalpha, p))
                poids_couche_t = (net * list_g_reels[i]) / 1000000
                dispatch_rows.append({
                    "Période Production": periode, "Ref. Qualité": ref, "Laize (mm)": laize,
                    "Type Papier": type_papier, "Couche": list_roles[i], "Poids Couche (T)": poids_couche_t
                })

    df_mrp_final = pd.DataFrame(mrp_results)
    df_dispatch_final = pd.DataFrame(dispatch_rows)

    # --- KPI GÉNÉRAUX ---
        # --- KPI GÉNÉRAUX (CORRIGÉ POUR ÉVITER L'ATTRIBUTEERROR) ---
    tot_net_m2 = df_mrp_final["Besoin Net (m²)"].sum()
    tot_tonnes = df_mrp_final["Poids Requis (T)"].sum()
    tot_colle_kg = df_mrp_final["Consommation Colle (kg)"].sum()
    
    # Création des colonnes sous forme de liste
    nombre_de_colonnes = 6 if afficher_finance else 4
    kpi_cols = st.columns(nombre_de_colonnes)
    
    # Remplissage de chaque colonne par son index [0, 1, 2, ...]
    kpi_cols[0].metric("Surface Nette", f"{tot_net_m2:,} m²")
    kpi_cols[1].metric("Tonnage Papier", f"{tot_tonnes:.2f} T")
    kpi_cols[2].metric("Poids Amidon Sec", f"{tot_colle_kg:,.0f} kg")
    kpi_cols[3].metric("Bobines Physiques", f"{int(np.ceil(tot_tonnes / poids_bobine_std))}")
    
    if afficher_finance:
        ca_total = df_mrp_final["CA Estimé (€)"].sum()
        marge_globale = df_mrp_final["Marge Brute (€)"].sum()
        kpi_cols[4].metric("Chiffre d'Affaires", f"{ca_total:,.0f} €")
        kpi_cols[5].metric("Marge Nette Matières", f"{marge_globale:,.0f} €", f"{(marge_globale/ca_total*100):.1f}%")

    # BOUTON DE TÉLÉCHARGEMENT EXCEL
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        df_mrp_final[["Période", "Ref. Qualité", "Composition", "Grammage (g/m²)", "Besoin Brut (m²)", "Besoin Net (m²)", "Poids Requis (T)"]].to_excel(writer, sheet_name='Plan Directeur', index=False)
        df_dispatch_final.to_excel(writer, sheet_name='Explosion 7 Couches', index=False)
        df_mrp_final[["Période", "Ref. Qualité", "Laize (mm)", "Poses", "Chute (mm)", "% Chute", "Poids Chute (T)"]].to_excel(writer, sheet_name='Optimisation Laizes', index=False)
        if afficher_finance:
            df_mrp_final[["Période", "Ref. Qualité", "CA Estimé (€)", "Coût Matière (€)", "Coût Colle (€)", "Perte Chute (€)", "Marge Brute (€)"]].to_excel(writer, sheet_name='Analyse Financière', index=False)
    
    st.download_button(
        label="📥 Télécharger le Rapport Industriel Expert (Excel Multi-Onglets)",
        data=buffer.getvalue(),
        file_name="rapport_nexus_mrp_complet.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # --- STRUCTURE DES ONGLETS ---
    tab1, tab2, tab3 = st.tabs(["📋 Planification & Calculs MRP", "📐 Efficacité Atelier (Trim & Colle)", "📊 Dashboard Direction / Finance"])
    
    with tab1:
        st.subheader("Plan Directeur de Production")
