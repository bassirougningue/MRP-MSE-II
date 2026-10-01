import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO

# Imports requis pour la génération de PDF professionnelle
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# Configuration de la page Streamlit
st.set_page_config(layout="wide", page_title="MRP Carton Ondulé Pro")

# --- CONSTANTES ET FACTEURS TECHNIQUES ---
FACTEURS_ONDULATION = {"A": 1.50, "C": 1.43, "B": 1.32, "E": 1.25}
CONSOMMATION_COLLE_BASE = {"A": 3.5, "C": 4.0, "B": 4.8, "E": 5.5} 

def decomposer_composition_dynamique(chaine_comp, combo_cannelure):
    """Calcule le grammage réel et la colle au m² de façon sécurisée"""
    try:
        papiers = str(chaine_comp).split('-')
        grammages = [int(''.join(filter(str.isdigit, p))) for p in papiers]
        cannelures_list = list(str(combo_cannelure).upper())
        
        roles = []
        grammages_reels = []
        colle_m2_total = 0 
        cannelure_index = 0
        
        for i in range(len(grammages)):
            if i % 2 == 0:
                if i == 0: roles.append("Liner Extérieur")
                elif i == len(grammages) - 1: roles.append("Liner Intérieur")
                else: roles.append(f"Médium Intermédiaire {i//2}")
                grammages_reels.append(grammages[i])
            else:
                flute_active = cannelures_list[cannelure_index] if cannelure_index < len(cannelures_list) else "C"
                roles.append(f"Cannelure {flute_active}")
                coeff = FACTEURS_ONDULATION.get(flute_active, 1.35)
                grammages_reels.append(round(grammages[i] * coeff))
                colle_m2_total += CONSOMMATION_COLLE_BASE.get(flute_active, 4.0) * coeff * 2
                cannelure_index += 1
                
        return sum(grammages_reels), grammages_reels, roles, round(colle_m2_total, 1)
    except:
        return 450, [140, 140, 140], ["Liner Ext", "Cannelure", "Liner Int"], 8.0

def generer_pdf_fiche_poste(df_mrp):
    """Génère un rapport PDF formaté pour les conducteurs d'onduleuse"""
    buffer_pdf = BytesIO()
    doc = SimpleDocTemplate(buffer_pdf, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=20, leading=24, textColor=colors.HexColor('#1f4e79'), spaceAfter=15)
    text_style = ParagraphStyle('TextStyle', parent=styles['Normal'], fontSize=10, leading=14)
    header_style = ParagraphStyle('HeaderStyle', parent=styles['Normal'], fontSize=10, fontName='Helvetica-Bold', textColor=colors.white)
    
    # En-tête du document
    story.append(Paragraph("🏭 FICHE DE POSTE CONDUCTEUR — PLAN ONDULEUSE", title_style))
    story.append(Paragraph("Généré automatiquement par CorruPlan Nexus Enterprise. Rapport de charge machine.", text_style))
    story.append(Spacer(1, 15))
    
    # Préparation du tableau de données pour le PDF
    table_data = [
        [Paragraph("Période", header_style), Paragraph("Réf", header_style), Paragraph("Composition", header_style), 
         Paragraph("Laize (mm)", header_style), Paragraph("Métrage (ml)", header_style), Paragraph("Durée Estimée", header_style)]
    ]
    
    for _, row in df_mrp.iterrows():
        table_data.append([
            Paragraph(str(row["Période"]), text_style),
            Paragraph(str(row["Ref. Qualité"]), text_style),
            Paragraph(str(row["Composition"]), text_style),
            Paragraph(f"{row['Laize (mm)']:.0f}", text_style),
            Paragraph(f"{row['Métrage Machine (ml)']:.0f} ml", text_style),
            Paragraph(str(row["Temps Machine (HH:MM)"]), text_style)
        ])
        
    t = Table(table_data, colWidths=[55, 65, 170, 70, 80, 100])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1f4e79')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('TOPPADDING', (0,0), (-1,0), 6),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f2f2f2')]),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    
    story.append(t)
    doc.build(story)
    buffer_pdf.seek(0)
    return buffer_pdf.getvalue()

# --- INTERFACE ---
st.title("📦 CorruPlan Nexus Enterprise — MES & MRP II")
st.markdown("Calcul dynamique des besoins nets, gâche de laize (*Trim Loss*) et rentabilité d'atelier.")

# --- BARRE LATÉRALE ---
st.sidebar.header("🛠️ Configuration Usine")
moq_limit = st.sidebar.number_input("Minimum de Commande Papier (MOQ en T)", value=2.5, step=0.5)
roll_weight = st.sidebar.number_input("Poids Moyen d'une Bobine (Tonnes)", value=1.5, step=0.1)

# ADD-ON 2 : Vitesse de défilement de l'onduleuse pour le MES
st.sidebar.markdown("---")
st.sidebar.header("⚡ Performance Machine")
vitesse_machine = st.sidebar.number_input("Vitesse de l'Onduleuse (m/min)", value=200, min_value=10, max_value=500, step=10)

st.sidebar.markdown("---")
st.sidebar.header("💰 Contrôle Financier")
afficher_finance = st.sidebar.toggle("💵 Activer la vue financière", value=True)

if afficher_finance:
    cout_tonne = st.sidebar.number_input("Coût Moyen Papier / Tonne (€)", value=880, step=50)
    prix_m2 = st.sidebar.number_input("Prix de Vente Moyen m² Fini (€)", value=1.45, step=0.1)
    cout_colle_kg = st.sidebar.number_input("Coût de l'Amidon sec (€/kg)", value=0.45, step=0.05)
else:
    cout_tonne, prix_m2, cout_colle_kg = 0, 0, 0

st.sidebar.markdown("---")
st.sidebar.header("📂 Source des Données")

mode_import = st.sidebar.radio(
    "Sélectionner la source :", 
    ["Plan de Démo (10 Lignes)", "Uploader un fichier (Excel)"],
    index=0
)

# Gabarit Excel
template_df = pd.DataFrame({
    "Ref. Qualité": ["201A", "302C", "501BCE"],
    "Cannelure": ["A", "C", "BCE"],
    "Composition": ["TL140-HP140-TL140", "KL175-SC150-TL150", "KL250-HP160-TL150-SC160-TL150-HP160-TL200"],
    "Laize (mm)": [2200, 2200, 2500],
    "Largeur À Plat (mm)": [420, 580, 800],
    "Période": ["J+1", "J+1", "J+2"],
    "Besoin Brut (m²)": [5000, 3500, 4000],
    "Stock Initial (m²)": [1200, 500, 0],
    "Tolérance (%)": [5, 5, 10]
})

buffer_template = BytesIO()
with pd.ExcelWriter(buffer_template, engine='xlsxwriter') as writer_t:
    template_df.to_excel(writer_t, sheet_name='Gabarit_Production', index=False)

st.sidebar.download_button(
    label="📥 Télécharger le modèle Excel (.xlsx)",
    data=buffer_template.getvalue(),
    file_name="modele_import_corruplan.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

df_source = pd.DataFrame()

# Chargement du Plan de Démo
if mode_import == "Plan de Démo (10 Lignes)":
    df_source = pd.DataFrame({
        "Ref. Qualité": ["201A", "201A", "302C", "302C", "401BC", "401BC", "402EB", "501BCE", "101E", "102B"],
        "Cannelure": ["A", "A", "C", "C", "BC", "BC", "EB", "BCE", "E", "B"],
        "Composition": [
            "TL140-HP140-TL140", "TL140-HP140-TL140", 
            "KL175-SC150-TL150", "KL175-SC150-TL150",
            "KL200-HP150-TL150-SC150-TL175", "KL200-HP150-TL150-SC150-TL175",
            "WKL140-HP120-TL120-HP140-TL140",
            "KL250-HP160-TL150-SC160-TL150-HP160-TL200", 
            "WKL120-HP100-TL100", "TL120-HP120-TL120"
        ],
        "Laize (mm)":,
        "Laize (mm)": [2200, 2200, 2200, 2200, 2500, 2500, 2200, 2500, 2200, 2200],
        "Largeur À Plat (mm)": [420, 420, 580, 580, 610, 610, 440, 800, 310, 520],
        "Période": ["J+1", "J+2", "J+1", "J+3", "J+1", "J+2", "J+2", "J+2", "J+1", "J+3"],
        "Besoin Brut (m²)": [1500, 2000, 8000, 3000, 4500, 6000, 3500, 5000, 1200, 2500],
        "Stock Initial (m²)": [1000, 0, 900, 0, 1500, 0, 500, 0, 200, 600],
        "Tolérance (%)": [5, 5, 5, 5, 8, 8, 8, 10, 5, 5]
    })
else:
    fichier_charge = st.sidebar.file_uploader("Glissez votre fichier Excel ici", type=["xlsx"])
    if fichier_charge is not None:
        try:
            df_in = pd.read_excel(fichier_charge, sheet_name=0)
            df_in.columns = df_in.columns.astype(str).str.strip()
            
            # Anti-décalage Excel automatique
            if "Largeur À Plat (mm)" in df_in.columns and df_in["Largeur À Plat (mm)"].astype(str).str.contains("J\+", na=False).any():
                df_in["Tolérance (%)"] = df_in["Stock Initial (m²)"]
                df_in["Stock Initial (m²)"] = df_in["Besoin Brut (m²)"]
                df_in["Besoin Brut (m²)"] = df_in["Période"]
                df_in["Période"] = df_in["Largeur À Plat (mm)"]
                
                df_in["Largeur À Plat (mm)"] = 500.0
                df_in.loc[df_in["Ref. Qualité"].astype(str).str.contains("201A", na=False), "Largeur À Plat (mm)"] = 420.0
                df_in.loc[df_in["Ref. Qualité"].astype(str).str.contains("302C", na=False), "Largeur À Plat (mm)"] = 580.0
                df_in.loc[df_in["Ref. Qualité"].astype(str).str.contains("401BC", na=False), "Largeur À Plat (mm)"] = 610.0
                df_in.loc[df_in["Ref. Qualité"].astype(str).str.contains("501BCE", na=False), "Largeur À Plat (mm)"] = 800.0

            df_source = df_in.copy()
        except Exception as e:
            st.sidebar.error(f"Erreur d'analyse du fichier Excel : {e}")

# --- TIMELINE COMPILATION ET TABS ---
if afficher_finance:
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Calcul MRP & Éclatement Matières", 
        "🚛 Planning Logistique des Réceptions", 
        "🚨 Tableau d'Alerte Ruptures (+24h)",
        "💰 Analyse de Performance Financière"
    ])
else:
    tab1, tab2, tab3 = st.tabs([
        "📊 Calcul MRP & Éclatement Matières", 
        "🚛 Planning Logistique des Réceptions", 
        "🚨 Tableau d'Alerte Ruptures (+24h)"
])