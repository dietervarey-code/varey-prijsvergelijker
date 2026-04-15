import streamlit as st
import pandas as pd
from io import BytesIO

# ============================================
# PAGINA CONFIGURATIE
# ============================================
st.set_page_config(
    page_title="Varey Prijsvergelijker",
    page_icon="💰",
    layout="wide"
)

# ============================================
# STYLING
# ============================================
st.markdown("""
    <style>
    .big-number {
        font-size: 2rem;
        font-weight: bold;
    }
    .price-up { color: #ff4b4b; }
    .price-down { color: #00cc66; }
    .price-same { color: #888888; }
    </style>
""", unsafe_allow_html=True)

# ============================================
# HEADER
# ============================================
st.title("💰 Varey Prijsvergelijker")
st.markdown("*Vergelijk uw artikelprijzen met leverancierlijsten in enkele klikken*")
st.divider()

# ============================================
# FUNCTIES
# ============================================
def load_file(uploaded_file):
    """Laad CSV of Excel bestand"""
    if uploaded_file is None:
        return None
    
    try:
        if uploaded_file.name.endswith('.csv'):
            # Probeer verschillende encodings
            try:
                df = pd.read_csv(uploaded_file, sep=None, engine='python')
            except:
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, encoding='latin-1', sep=None, engine='python')
        else:
            df = pd.read_excel(uploaded_file)
        return df
    except Exception as e:
        st.error(f"Fout bij laden: {e}")
        return None

def convert_to_excel(df):
    """Converteer DataFrame naar Excel voor download"""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Prijsvergelijking')
        
        # Opmaak toevoegen
        workbook = writer.book
        worksheet = writer.sheets['Prijsvergelijking']
        
        # Formaten definiëren
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#4472C4',
            'font_color': 'white',
            'border': 1
        })
        
        price_up_format = workbook.add_format({
            'bg_color': '#FFCCCC',
            'num_format': '€ #,##0.00'
        })
        
        price_down_format = workbook.add_format({
            'bg_color': '#CCFFCC', 
            'num_format': '€ #,##0.00'
        })
        
        # Headers opmaken
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_format)
        
        # Kolombreedte aanpassen
        for i, col in enumerate(df.columns):
            max_length = max(df[col].astype(str).map(len).max(), len(col)) + 2
            worksheet.set_column(i, i, min(max_length, 30))
    
    return output.getvalue()

def convert_to_csv(df):
    """Converteer DataFrame naar CSV voor download"""
    return df.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')

# ============================================
# STAP 1: BESTANDEN UPLOADEN
# ============================================
st.header("📁 Stap 1: Bestanden uploaden")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Uw artikellijst")
    own_file = st.file_uploader(
        "Upload uw Excel/CSV met huidige prijzen",
        type=['xlsx', 'xls', 'csv'],
        key="own_file"
    )
    own_df = load_file(own_file)
    
    if own_df is not None:
        st.success(f"✅ {len(own_df)} rijen geladen")
        with st.expander("🔍 Bekijk data"):
            st.dataframe(own_df.head(10), use_container_width=True)

with col2:
    st.subheader("Leverancier prijslijst")
    supplier_file = st.file_uploader(
        "Upload de Excel/CSV van de leverancier",
        type=['xlsx', 'xls', 'csv'],
        key="supplier_file"
    )
    supplier_df = load_file(supplier_file)
    
    if supplier_df is not None:
        st.success(f"✅ {len(supplier_df)} rijen geladen")
        with st.expander("🔍 Bekijk data"):
            st.dataframe(supplier_df.head(10), use_container_width=True)

# ============================================
# STAP 2: KOLOMMEN MATCHEN
# ============================================
if own_df is not None and supplier_df is not None:
    st.divider()
    st.header("🔗 Stap 2: Kolommen koppelen")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Uw bestand")
        own_article_col = st.selectbox(
            "Kolom met artikelnummer/code:",
            options=own_df.columns,
            key="own_article"
        )
        own_price_col = st.selectbox(
            "Kolom met huidige prijs:",
            options=own_df.columns,
            key="own_price"
        )
        # Optioneel: extra kolommen meenemen
        own_extra_cols = st.multiselect(
            "Extra kolommen meenemen (optioneel):",
            options=[c for c in own_df.columns if c not in [own_article_col, own_price_col]],
            key="own_extra"
        )
    
    with col2:
        st.subheader("Leverancier bestand")
        supplier_article_col = st.selectbox(
            "Kolom met artikelnummer/code:",
            options=supplier_df.columns,
            key="supplier_article"
        )
        supplier_price_col = st.selectbox(
            "Kolom met nieuwe prijs:",
            options=supplier_df.columns,
            key="supplier_price"
        )

    # ============================================
    # STAP 3: VERGELIJKEN
    # ============================================
    st.divider()
    
    if st.button("🔍 Vergelijk prijzen", type="primary", use_container_width=True):
        
        with st.spinner("Bezig met vergelijken..."):
            
            # Maak kopieën en bereid data voor
            own_data = own_df.copy()
            supplier_data = supplier_df.copy()
            
            # Converteer artikelnummers naar string voor matching
            own_data['_match_key'] = own_data[own_article_col].astype(str).str.strip().str.upper()
            supplier_data['_match_key'] = supplier_data[supplier_article_col].astype(str).str.strip().str.upper()
            
            # Converteer prijzen naar numeriek
            own_data['_own_price'] = pd.to_numeric(
                own_data[own_price_col].astype(str).str.replace(',', '.').str.replace('€', '').str.strip(),
                errors='coerce'
            )
            supplier_data['_supplier_price'] = pd.to_numeric(
                supplier_data[supplier_price_col].astype(str).str.replace(',', '.').str.replace('€', '').str.strip(),
                errors='coerce'
            )
            
            # Selecteer relevante kolommen van leverancier
            supplier_subset = supplier_data[['_match_key', '_supplier_price']].drop_duplicates(subset='_match_key')
            
            # Merge datasets
            result = own_data.merge(
                supplier_subset,
                on='_match_key',
                how='left'
            )
            
            # Bereken verschil
            result['Verschil €'] = result['_supplier_price'] - result['_own_price']
            result['Verschil %'] = ((result['_supplier_price'] - result['_own_price']) / result['_own_price'] * 100).round(2)
            
            # Categoriseer
            def categorize(row):
                if pd.isna(row['_supplier_price']):
                    return '⚠️ Niet gevonden'
                elif row['Verschil €'] > 0.01:
                    return '🔴 Prijsverhoging'
                elif row['Verschil €'] < -0.01:
                    return '🟢 Prijsverlaging'
                else:
                    return '⚪ Ongewijzigd'
            
            result['Status'] = result.apply(categorize, axis=1)
            
            # Maak nette output
            output_cols = [own_article_col] + own_extra_cols + [own_price_col]
            
            final_result = result[output_cols + ['_supplier_price', 'Verschil €', 'Verschil %', 'Status']].copy()
            final_result.columns = [own_article_col] + own_extra_cols + [
                'Huidige prijs', 'Nieuwe prijs', 'Verschil €', 'Verschil %', 'Status'
            ]
            
            # Sla resultaat op in session state voor later gebruik
            st.session_state['final_result'] = final_result
            st.session_state['result_stats'] = {
                'total_matched': result['_supplier_price'].notna().sum(),
                'total_not_found': result['_supplier_price'].isna().sum(),
                'price_increases': (result['Verschil €'] > 0.01).sum(),
                'price_decreases': (result['Verschil €'] < -0.01).sum(),
                'unchanged': ((result['Verschil €'] >= -0.01) & (result['Verschil €'] <= 0.01) & result['_supplier_price'].notna()).sum(),
                'total_increase': result[result['Verschil €'] > 0]['Verschil €'].sum(),
                'total_decrease': result[result['Verschil €'] < 0]['Verschil €'].sum()
            }

# ============================================
# RESULTATEN TONEN
# ============================================
if 'final_result' in st.session_state:
    final_result = st.session_state['final_result']
    stats = st.session_state['result_stats']
    
    st.header("📊 Resultaten")
    
    # Statistieken
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Totaal gematcht", f"{stats['total_matched']:,}")
    m2.metric("Prijsverhogingen", f"{stats['price_increases']:,}", f"+€{stats['total_increase']:,.2f}")
    m3.metric("Prijsverlagingen", f"{stats['price_decreases']:,}", f"-€{abs(stats['total_decrease']):,.2f}")
    m4.metric("Ongewijzigd", f"{stats['unchanged']:,}")
    m5.metric("Niet gevonden", f"{stats['total_not_found']:,}")
    
    st.divider()
    
    # Filter opties
    filter_option = st.selectbox(
        "Toon:",
        options=[
            "Alle resultaten",
            "🔴 Alleen prijsverhogingen",
            "🟢 Alleen prijsverlagingen",
            "🔴🟢 Alle wijzigingen",
            "⚠️ Niet gevonden"
        ]
    )
    
    # Filter toepassen
    if filter_option == "🔴 Alleen prijsverhogingen":
        display_df = final_result[final_result['Status'] == '🔴 Prijsverhoging']
    elif filter_option == "🟢 Alleen prijsverlagingen":
        display_df = final_result[final_result['Status'] == '🟢 Prijsverlaging']
    elif filter_option == "🔴🟢 Alle wijzigingen":
        display_df = final_result[final_result['Status'].isin(['🔴 Prijsverhoging', '🟢 Prijsverlaging'])]
    elif filter_option == "⚠️ Niet gevonden":
        display_df = final_result[final_result['Status'] == '⚠️ Niet gevonden']
    else:
        display_df = final_result
    
    # Sorteer opties
    sort_col = st.selectbox(
        "Sorteer op:",
        options=['Verschil €', 'Verschil %', 'Huidige prijs', 'Nieuwe prijs', 'Status'],
        index=0
    )
    sort_order = st.radio("Volgorde:", ['Aflopend', 'Oplopend'], horizontal=True)
    
    display_df = display_df.sort_values(
        by=sort_col, 
        ascending=(sort_order == 'Oplopend'),
        na_position='last'
    )
    
    # Toon aantal resultaten
    st.info(f"📋 {len(display_df)} artikelen gevonden met huidige filter")
    
    # Toon tabel
    st.dataframe(
        display_df,
        use_container_width=True,
        height=400,
        column_config={
            "Huidige prijs": st.column_config.NumberColumn(format="€ %.2f"),
            "Nieuwe prijs": st.column_config.NumberColumn(format="€ %.2f"),
            "Verschil €": st.column_config.NumberColumn(format="€ %.2f"),
            "Verschil %": st.column_config.NumberColumn(format="%.2f %%"),
        }
    )
    
    st.divider()
    
    # ============================================
    # DOWNLOAD OPTIES
    # ============================================
    st.subheader("📥 Exporteren")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.download_button(
            label="📥 Download alles (Excel)",
            data=convert_to_excel(final_result),
            file_name="prijsvergelijking_compleet.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    
    with col2:
        # Alleen wijzigingen
        changes_only = final_result[final_result['Status'].isin(['🔴 Prijsverhoging', '🟢 Prijsverlaging'])]
        st.download_button(
            label="📥 Alleen wijzigingen (Excel)",
            data=convert_to_excel(changes_only),
            file_name="prijswijzigingen.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    
    with col3:
        st.download_button(
            label="📥 Download als CSV",
            data=convert_to_csv(final_result),
            file_name="prijsvergelijking.csv",
            mime="text/csv"
        )
    
    # ============================================
