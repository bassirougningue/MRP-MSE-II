import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# Configuration de la page Streamlit
st.set_page_config(layout="wide", page_title="MRP Carton Ondulé")

st.title("📦 Module MRP Avancé — Onduleuse & Bobines")
st.markdown("Calcul dynamique des besoins nets, éclatement par laize et gestion des risques logistiques.")

# 1. Barre latérale : Paramètres de configuration industriels
st.sidebar.header("🛠️ Configuration Usine")
moq_limit = st.sidebar.number_input("Minimum de Commande Papetier (MOQ en T)", value=2.5, step=0.5)
roll_weight = st.sidebar.number_input("Poids Moyen d'une Bobine (Tonnes)", value=1.0, step=0.1)

# Organisation de l'affichage en Onglets (Tabs)
tab1, tab2, tab3 = st.tabs([
    "📊 Calcul MRP & Éclatement Matières", 
    "🚛 Planning Logistique des Réceptions", 
    "🚨 Tableau d'Alerte Ruptures (+24h)"
])

# ONGLET 1 : Calculs MRP de base et répartition par type de papier
with tab1:
    st.subheader("Plan de Production Synthétique (Horizon J+1 à J+5)")
    
    mrp_df = pd.DataFrame({
        "Ref. Qualité": ["201A", "201A", "302C", "401BC"],
        "Composition": ["TL140-HP140-TL140", "TL140-HP140-TL140", "KL175-SC150-TL150", "KL200-HP150-TL150-SC150-TL175"],
        "Grammage Réel (g/m²)": [490, 490, 539, 937],
        "Laize Réelle (mm)": [2200, 2200, 2200, 2500],
        "Période": ["J+1", "J+2", "J+1", "J+1"],
        "Besoin Brut (m²)": [1500, 2000, 8000, 3000],
        "Besoin Net (m²)": [300, 2000, 5500, 2000],
        "Poids Requis (Tonnes)": [0.147, 0.980, 2.965, 1.874]
    })
    
    st.dataframe(mrp_df, use_container_width=True)
    
    # Graphique analytique de répartition globale
    dispatch_data = pd.DataFrame({
        "Type Papier": ["TL (Testliner)", "SC (Semi-chimique)", "KL (Kraftliner)", "HP (High Perf. Fluting)"],
        "Tonnage Total": [7.334, 5.361, 4.676, 3.489]
    })
    fig_pie = px.pie(dispatch_data, values="Tonnage Total", names="Type Papier", 
                     title="Allocation Globale des Papiers (Toutes Laizes confondues)",
                     color_discrete_sequence=px.colors.qualitative.Pastel)
    st.plotly_chart(fig_pie, use_container_width=True)

# ONGLET 2 : Intégration logistique avec calcul du nombre de bobines réelles
with tab2:
    st.subheader("Planning de Déchargement à Quai & Formatage Bobines")
    st.markdown("Ce tableau convertit les tonnages bruts en **nombre d'unités physiques (bobines)** à manipuler au chariot élévateur.")
    
    rec_df = pd.DataFrame({
        "Jour Réception": ["J+1", "J+1", "J+1", "J+1", "J+1", "J+1", "J+1", "J+2"],
        "Laize Bobine (mm)": [2200, 2200, 2200, 2200, 2500, 2500, 2500, 2200],
        "Type Papier": ["TL", "HP", "SC", "KL", "TL", "SC", "KL", "TL"],
        "Poids Attendu (T)": [0.867, 0.063, 2.474, 1.514, 1.190, 2.887, 3.162, 3.670]
    })
    
    # Calcul dynamique basé sur l'input utilisateur de la sidebar
    rec_df["Nombre de Bobines (Est.)"] = np.ceil(rec_df["Poids Attendu (T)"] / roll_weight).astype(int)
    
    st.dataframe(rec_df, use_container_width=True)
    
    # Visualisation de la charge de travail du quai
    fig_bar = px.bar(rec_df, x="Jour Réception", y="Poids Attendu (T)", color="Type Papier", 
                     title="Profil de Charge Quotidien des Réceptions (Tonnes)", barmode="stack")
    st.plotly_chart(fig_bar, use_container_width=True)

# ONGLET 3 : Tableau de bord de gestion des risques (Alerte Rupture)
with tab3:
    st.subheader("⚠️ Simulation de Stress-Test Logistique : Retard Fournisseur (+24h)")
    st.info("Ce modèle simule l'impact immédiat sur l'onduleuse si un camion de livraison à J+1 subit un décalage de 24 heures.")
    
    rupture_df = pd.DataFrame({
        "Période Impactée": ["J+1", "J+1", "J+1"],
        "Ligne Ordonnancée / Réf": ["onduleuse - Réf 201A", "onduleuse - Réf 302C", "onduleuse - Réf 401BC"],
        "Composant Bloquant": ["TL (Laize 2200)", "KL (Laize 2200)", "SC (Laize 2500)"],
        "Déficit Immédiat (m²)": ["-300 m²", "-5 500 m²", "-2 000 m²"],
        "Statut Production": ["🔴 ARRÊT DE LIGNE (Rupture)", "🔴 ARRÊT DE LIGNE (Rupture)", "🟡 Risque Modéré (Stock Sécurité bas)"]
    })
    st.table(rupture_df)
