import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

# Paramétrage de la page professionnelle
st.set_page_config(page_title="ROCHCorr BI & Optimization", page_icon="📈", layout="wide")

# --- PARAMÈTRES ET CONSTANTES TECHNIQUES ---
FACTEURS_ONDULATION = {"A": 1.50, "C": 1.43, "B": 1.32, "E": 1.25}

# --- FONCTIONS DE CALCUL CONJOINT (MRP, TRIM & FINANCE) ---
def analyser_mrp_complet(df_prod, cout_moyen_t, prix_vente_m2):
    results = []
    stocks = {"201A": 1200, "302C": 2500, "401BC": 1000} # État initial fixe
    
    for idx, row in df_prod.iterrows():
        ref = row["Ref. Qualité"]
        brut = row["Besoin Brut (m²)"]
        cannelure = row["Cannelure"]
        comp_str = row["Composition"]
        laize = row["Laize (mm)"]
        w_box = row["Largeur À Plat (mm)"]
        periode = row["Période"]
        
        # 1. Calcul MRP (Besoin Net)
        stk_disp = stocks.get(ref, 0)
        if stk_disp >= brut:
            net = 0
            stocks[ref] = stk_disp - brut
        else:
            net = brut - stk_disp
            stocks[ref] = 0
            
        # 2. Décomposition Grammage & Calcul Poids
        papiers = comp_str.split('-')
        grammages = [int(''.join(filter(str.isdigit, p))) for p in papiers]
        coeff = FACTEURS_ONDULATION.get(cannelure, 1.35)
        g_tot = sum(grammages) + (grammages[1] * (coeff - 1)) if len(grammages) == 3 else sum(grammages) # Fallback simplifié
        if len(grammages) == 5: # Double-wall
            g_tot = grammages[0] + (grammages[1]*coeff) + grammages[2] + (grammages[3]*coeff) + grammages[4]
            
        poids_brut_t = (net * g_tot) / 1000000
        
        # 3. Optimisation de la Laize (Trim Loss)
        nb_poses = int(laize // w_box)
        largeur_utile = nb_poses * w_box
        chute_laize_mm = laize - largeur_utile
        pct_chute = (chute_laize_mm / laize) * 100 if net > 0 else 0
        poids_chute_t = poids_brut_t * (pct_chute / 100)
        poids_utile_t = poids_brut_t - poids_chute_t
        
        # 4. Modélisation Financière
        cout_matiere = poids_brut_t * cout_moyen_t
        cout_perte_chute = poids_chute_t * cout_moyen_t
        chiffre_affaires = net * prix_vente_m2
        marge_brute = chiffre_affaires - cout_matiere
        
        results.append({
            "Période": periode, "Réf": ref, "Besoin Net (m²)": net, "Laize (mm)": laize,
            "Largeur Produit (mm)": w_box, "Poses": nb_poses, "Chute (mm)": chute_laize_mm,
            "% Chute": round(pct_chute, 2), "Poids Total (T)": round(poids_brut_t, 3),
            "Poids Chute (T)": round(poids_chute_t, 3), "Coût Matière (€)": round(cout_matiere, 2),
            "Perte Chute (€)": round(cout_perte_chute, 2), "CA Estimé (€)": round(chiffre_affaires, 2),
            "Marge Brute (€)": round(marge_brute, 2)
        })
    return pd.DataFrame(results)

# --- INTERFACE DE L'APPLICATION ---
st.title("📈 Tableau de Bord Financier & Optimisation des Chutes")
st.caption("Analyse de la rentabilité matière et taux de valorisation des laizes pour ondulatrice")

# Barre latérale : Saisie des variables financières de l'entreprise
st.sidebar.header("💰 Paramètres Économiques")
cout_tonne = st.sidebar.number_input("Coût Moyen du Papier / Tonne (€)", value=850, step=50)
prix_m2 = st.sidebar.number_input("Prix de Vente Moyen du m² Fini (€)", value=1.20, step=0.1)

# Jeu de données enrichi avec les dimensions nécessaires au calcul géométrique des poses
df_production_brute = pd.DataFrame({
    "Ref. Qualité": ["201A", "201A", "302C", "401BC", "302C"],
    "Cannelure": ["A", "A", "C", "B", "C"],
    "Composition": ["TL140-HP140-TL140", "TL140-HP140-TL140", "KL175-SC150-TL150", "KL200-HP150-TL150-SC150-TL175", "KL175-SC150-TL150"],
    "Laize (mm)": [2200, 2200, 2200, 2500, 2200],
    "Largeur À Plat (mm)": [420, 420, 580, 780, 580], # Dimension physique de la plaque dépliée
    "Période": ["J+1", "J+2", "J+1", "J+1", "J+3"],
    "Besoin Brut (m²)": [1500, 2000, 8000, 3000, 4500]
})

# Lancement des calculs financiers et géométriques
df_bi = analyser_mrp_complet(df_production_brute, cout_tonne, prix_m2)

# --- AFFICHAGE FINANCIER & PERFORMANCE ---
ca_total = df_bi["CA Estimé (€)"].sum()
cout_mat_total = df_bi["Coût Matière (€)"].sum()
perte_chute_totale = df_bi["Perte Chute (€)"].sum()
marge_globale = df_bi["Marge Brute (€)"].sum()
taux_gache_moyen = df_bi["Poids Chute (T)"].sum() / df_bi["Poids Total (T)"].sum() * 100

col1, col2, col3, col4 = st.columns(4)
col1.metric("Chiffre d'Affaires Projeté", f"{ca_total:,.2f} €")
col2.metric("Marge Brute (Matière)", f"{marge_globale:,.2f} €", delta=f"{(marge_globale/ca_total*100):.1f}% Marge")
col3.metric("Coût de la Chute de Laize", f"{perte_chute_totale:,.2f} €", delta=f"-{perte_chute_totale:.2f}€ Perdus", delta_color="inverse")
col4.metric("Taux de Gâche Moyen", f"{taux_gache_moyen:.2f} %")

tab_perf, tab_trim = st.tabs(["💰 Évaluation de la Rentabilité", "📐 Rapport d'Optimisation des Poses"])

with tab_perf:
    st.subheader("Analyse Financière des Marges par Référence")
    st.dataframe(df_bi[["Période", "Réf", "Poids Total (T)", "CA Estimé (€)", "Coût Matière (€)", "Perte Chute (€)", "Marge Brute (€)"]], use_container_width=True, hide_index=True)
    
    # Graphique de rentabilité cumulée
    fig_waterfall = go.Figure(go.Waterfall(
        name = "Cascade de Marge", orientation = "v",
        measure = ["relative", "relative", "relative", "total"],
        x = ["Chiffre d'Affaires", "Coût Papiers Utiles", "Coût Chute (Trim Loss)", "Marge Finale (EBIT)"],
        textposition = "outside",
        text = [f"+{ca_total:,.0f}€", f"-{(cout_mat_total-perte_chute_totale):,.0f}€", f"-{perte_chute_totale:,.0f}€", f"{marge_globale:,.0f}€"],
        y = [ca_total, -(cout_mat_total - perte_chute_totale), -perte_chute_totale, 0],
        connector = {"line":{"color":"rgb(63, 63, 63)"}},
    ))
    fig_waterfall.update_layout(title="Décomposition de la Valeur Générée par le Plan de Production (€)")
    st.plotly_chart(fig_waterfall, use_container_width=True)

with tab_trim:
    st.subheader("Rapport d'Efficacité Géométrique de l'Ondulatrice")
    st.markdown("Ce tableau met en évidence l'écart entre la laize de bobine chargée et la largeur totale consommée par vos outils de découpe.")
    
    st.dataframe(df_bi[["Période", "Réf", "Laize (mm)", "Largeur Produit (mm)", "Poses", "Chute (mm)", "% Chute", "Poids Chute (T)"]], use_container_width=True, hide_index=True)
    
    # Graphique de gâche par référence
    fig_chute = px.bar(df_bi, x="Réf", y="% Chute", color="Période", title="Perte de Papier Linéaire par Format Produit (%)", text="% Chute")
    st.plotly_chart(fig_chute, use_container_width=True)
