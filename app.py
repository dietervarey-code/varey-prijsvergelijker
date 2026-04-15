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
    """Laad CSV of Excel bestand - ALLES als tekst om voorloopnullen te behouden"""
    if uploaded_file is None:
        return None
    
    try:
        if uploaded_file.name.endswith('.csv'):
            # CSV: laad alles als string
            try:
                df = pd.read_csv(uploaded_file, sep=None, engine='python', dtype=str, keep_default_na=False)
            except:
                uploaded_file.seek(0)
                try:
                    df = pd.read_csv(uploaded_file, encoding='latin-1', sep=None, engine='python', dtype=str, keep_default_na=False)
                except:
                    uploaded_file.seek(0)
                    df = pd.read_csv(uploaded_file, encoding='cp1252', sep=';', dtype=str, keep_default_na=False)
        else:
            # Excel: laad alles als string
            try:
                df = pd.read_excel(uploaded_file, engine='openpyxl', dtype=str, keep_default_na=False)
            except:
                uploaded_file.seek(0)
                try:
                    from openpyxl import load_workbook
                    wb = load_workbook(uploaded_file, data_only=True, read_only=True)
                    ws = wb.active
                    data = list(ws.values)
                    if data:
                        headers = data[0]
                        rows = []
                        for row in data[1:]:
                            rows.append([str(cell) if cell is not None else '' for cell in row])
                        df = pd.DataFrame(rows, columns=headers)
                    else:
                        df = pd.DataFrame()
                    wb.close()
                except:
                    uploaded_file.seek(0)
                    try:
                        df = pd.read_excel(uploaded_file, engine='xlrd', dtype=str, keep_default_na=False)
                    except:
                        uploaded_file.seek(0)
                        df = pd.read_excel(uploaded_file, engine='calamine', dtype=str, keep_default_na=False)
        
        # Verwijder volledig lege rijen en kolommen
        df = df.dropna(how='all').dropna(axis=1, how='all')
        df = df.reset_index(drop=True)
        
        return df
    
    except Exception as e:
        st.error(f"Fout bij laden: {e}")
        return None

def clean_article_number(value):
    """
    Maak artikelnummer schoon voor matching:
    - Verwijder spaties
    - Verwijder .0 suffix (Excel float probleem)
    - Verwijder duizendtallen-separators (komma's en punten in verkeerde context)
    - Behoud voorloopnullen
    """
    if pd.isna(value) or value is None:
        return ''
    
    # Naar string
    s = str(value).strip()
    
    # Verwijder .0 aan het einde (Excel float probleem: 118910 -> 118910.0)
    if s.endswith('.0'):
        s = s[:-2]
    
    # Als het een getal is met duizendtallen-komma (Amerikaanse notatie): 118,910 -> 118910
    # Maar pas op: niet doen als er een punt in zit (dan kan het een decimaal zijn)
    if ',' in s and '.' not in s:
        # Check of het een duizendtallen-komma is (alleen cijfers en komma's)
        test = s.replace(',', '')
        if test.isdigit():
            s = test
    
    # Europese duizendtallen-punt: 118.910 -> 118910 (als geen komma aanwezig)
    if '.' in s and ',' not in s:
        test = s.replace('.', '')
        if test.isdigit() and len(s.split('.')[-1]) == 3:
            # Waarschijnlijk duizendtallen-punt
            s = test
    
    return s

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
        # Extra kolommen van leverancier meenemen
        supplier_extra_cols = st.multiselect(
            "Extra kolommen meenemen (optioneel):",
            options=[c for c in supplier_df.columns if c not in [supplier_article_col, supplier_price_col]],
            key="supplier_extra"
        )
    # ============================================
    # STAP 3: VERGELIJKEN
    # ============================================
    st.divider()
    
    if st.button("🔍 Vergelijk prijzen", type="primary", use_container_width=True):
        
        with st.spinner("Bezig met vergelijken..."):
            
            own_data = own_df.copy()
            supplier_data = supplier_df.copy()
            
            # ============================================
            # ARTIKELNUMMER MATCHING - ROBUUST
            # ============================================
            
            # Clean article numbers voor matching
            own_data['_match_key'] = own_data[own_article_col].apply(clean_article_number)
            supplier_data['_match_key'] = supplier_data[supplier_article_col].apply(clean_article_number)
            
            # Debug info tonen
            with st.expander("🔧 Debug: Bekijk match keys"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write("**Uw bestand (eerste 10):**")
                    st.write(own_data[[own_article_col, '_match_key']].head(10))
                with col2:
                    st.write("**Leverancier (eerste 10):**")
                    st.write(supplier_data[[supplier_article_col, '_match_key']].head(10))
            
            # ============================================
            # PRIJS CONVERSIE - ROBUUST
            # ============================================
            
            def clean_price(value):
                """Converteer prijs naar float, ongeacht formaat"""
                if pd.isna(value) or value is None or str(value).strip() == '':
                    return None
                
                s = str(value).strip()
                
                # Verwijder valuta symbolen en spaties
                s = s.replace('€', '').replace('$', '').replace(' ', '')
                
                # Bepaal decimaal separator
                # Als beide . en , aanwezig: laatste is decimaal
                if '.' in s and ',' in s:
                    if s.rfind('.') > s.rfind(','):
                        # Punt is decimaal (1,234.56)
                        s = s.replace(',', '')
                    else:
                        # Komma is decimaal (1.234,56)
                        s = s.replace('.', '').replace(',', '.')
                elif ',' in s:
                    # Alleen komma: check of het decimaal is
                    # Als er 3 cijfers na de komma zijn, is het waarschijnlijk duizendtallen
                    parts = s.split(',')
                    if len(parts) == 2 and len(parts[1]) == 3 and parts[0].replace('.', '').isdigit():
                        # Duizendtallen komma: 1,234 -> 1234
                        s = s.replace(',', '')
                    else:
                        # Decimaal komma: 12,34 -> 12.34
                        s = s.replace(',', '.')
                
                try:
                    return float(s)
                except:
                    return None
            
            own_data['_own_price'] = own_data[own_price_col].apply(clean_price)
            supplier_data['_supplier_price'] = supplier_data[supplier_price_col].apply(clean_price)
            
            # ============================================
            # MATCHING
            # ============================================
            
            # Verwijder lege match keys
            supplier_data_clean = supplier_data[supplier_data['_match_key'] != ''].copy()
            
            # Selecteer relevante kolommen van leverancier (neem eerste bij duplicaten)
            supplier_cols_to_keep = ['_match_key', '_supplier_price'] + supplier_extra_cols
            supplier_subset = supplier_data_clean[supplier_cols_to_keep].drop_duplicates(subset='_match_key', keep='first')
            
            # Merge datasets
            result = own_data.merge(
                supplier_subset,
                on='_match_key',
                how='left'
            )
            
            # ============================================
            # BEREKENINGEN
            # ============================================
            
            result['Verschil €'] = result['_supplier_price'] - result['_own_price']
            result['Verschil %'] = ((result['_supplier_price'] - result['_own_price']) / result['_own_price'] * 100).round(2)
            
            def categorize(row):
                if pd.isna(row['_supplier_price']):
                    return '⚠️ Niet gevonden'
                elif pd.isna(row['Verschil €']):
                    return '⚠️ Niet gevonden'
                elif row['Verschil €'] > 0.01:
                    return '🔴 Prijsverhoging'
                elif row['Verschil €'] < -0.01:
                    return '🟢 Prijsverlaging'
                else:
                    return '⚪ Ongewijzigd'
            
            result['Status'] = result.apply(categorize, axis=1)
            
            # ============================================
            # OUTPUT VOORBEREIDEN
            # ============================================
            
            output_cols = [own_article_col] + own_extra_cols + [own_price_col]
            
            # Voeg leverancier extra kolommen toe
            result_cols = output_cols + ['_supplier_price'] + supplier_extra_cols + ['Verschil €', 'Verschil %', 'Status']
            final_result = result[result_cols].copy()
            
            # Hernoem kolommen
            new_col_names = [own_article_col] + own_extra_cols + ['Huidige prijs', 'Nieuwe prijs'] + supplier_extra_cols + ['Verschil €', 'Verschil %', 'Status']
            final_result.columns = new_col_names
            
            # Sla op in session state
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
            # Bewaar voor exports
            st.session_state['supplier_extra_cols'] = supplier_extra_cols
            st.session_state['own_extra_cols'] = own_extra_cols
            
            # ============================================
            # NIET-GEMATCHTE ARTIKELEN VERZAMELEN
            # ============================================
            
            # Artikelen bij leverancier die NIET bij ons voorkomen
            matched_supplier_keys = set(result[result['_supplier_price'].notna()]['_match_key'])
            all_supplier_keys = set(supplier_data_clean['_match_key'])
            unmatched_supplier_keys = all_supplier_keys - matched_supplier_keys
            
            supplier_not_found = supplier_data_clean[supplier_data_clean['_match_key'].isin(unmatched_supplier_keys)].copy()
            # Selecteer originele kolommen voor export
            supplier_not_found_export_cols = [supplier_article_col, supplier_price_col] + supplier_extra_cols
            supplier_not_found_export = supplier_not_found[supplier_not_found_export_cols].copy()
            st.session_state['supplier_not_found'] = supplier_not_found_export
            
            # Artikelen bij ons die NIET bij leverancier voorkomen
            own_not_found = result[result['_supplier_price'].isna()].copy()
            own_not_found_export_cols = [own_article_col] + own_extra_cols + [own_price_col]
            own_not_found_export = own_not_found[own_not_found_export_cols].copy()
            st.session_state['own_not_found'] = own_not_found_export
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
    # Forceer artikelnummer als tekst in weergave
    display_df_styled = display_df.copy()
    
    # Alle kolommen behalve prijs-kolommen als tekst behandelen
    col_config = {
        "Huidige prijs": st.column_config.NumberColumn(format="€ %.2f"),
        "Nieuwe prijs": st.column_config.NumberColumn(format="€ %.2f"),
        "Verschil €": st.column_config.NumberColumn(format="€ %.2f"),
        "Verschil %": st.column_config.NumberColumn(format="%.2f %%"),
    }
    
    # Eerste kolom (artikelnummer) als tekst
    first_col = display_df.columns[0]
    col_config[first_col] = st.column_config.TextColumn(first_col)
    
    # Extra kolommen ook als tekst (eigen bestand)
    for col in own_extra_cols:
        if col in display_df.columns:
            col_config[col] = st.column_config.TextColumn(col)
    
    # Extra kolommen van leverancier ook als tekst
    if 'supplier_extra_cols' in st.session_state:
        for col in st.session_state['supplier_extra_cols']:
            if col in display_df.columns:
                col_config[col] = st.column_config.TextColumn(col)
    
    st.dataframe(
        display_df_styled,
        use_container_width=True,
        height=400,
        column_config=col_config
    )
    
    # Eerste kolom (artikelnummer) als tekst
    first_col = display_df.columns[0]
    col_config[first_col] = st.column_config.TextColumn(first_col)
    
    # Extra kolommen ook als tekst
    for col in own_extra_cols:
        if col in display_df.columns:
            col_config[col] = st.column_config.TextColumn(col)
    
    st.dataframe(
        display_df_styled,
        use_container_width=True,
        height=400,
        column_config=col_config
    )
    
    st.divider()
    
    # ============================================
    # DOWNLOAD OPTIES
    # ============================================
    st.subheader("📥 Exporteren")
    
    # Rij 1: Standaard exports
    st.markdown("**📊 Vergelijkingsresultaten:**")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.download_button(
            label="📥 Download alles (Excel)",
            data=convert_to_excel(final_result),
            file_name="prijsvergelijking_compleet.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    
    with col2:
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
    
    # Rij 2: Niet-gevonden exports
    st.divider()
    st.markdown("**🔍 Niet-gematchte artikelen:**")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Onze artikelen niet gevonden bij leverancier
        if 'own_not_found' in st.session_state:
            own_not_found = st.session_state['own_not_found']
            st.metric("Onze artikelen niet bij leverancier", len(own_not_found))
            
            if len(own_not_found) > 0:
                with st.expander("👀 Bekijk lijst"):
                    st.dataframe(own_not_found.head(20), use_container_width=True)
                
                st.download_button(
                    label="📥 Export: Onze artikelen NIET bij leverancier",
                    data=convert_to_excel(own_not_found),
                    file_name="onze_artikelen_niet_bij_leverancier.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="download_own_not_found"
                )
    
    with col2:
        # Leverancier artikelen niet gevonden bij ons
        if 'supplier_not_found' in st.session_state:
            supplier_not_found = st.session_state['supplier_not_found']
            st.metric("Leverancier artikelen niet bij ons", len(supplier_not_found))
            
            if len(supplier_not_found) > 0:
                with st.expander("👀 Bekijk lijst"):
                    st.dataframe(supplier_not_found.head(20), use_container_width=True)
                
                st.download_button(
                    label="📥 Export: Leverancier artikelen NIET bij ons",
                    data=convert_to_excel(supplier_not_found),
                    file_name="leverancier_artikelen_niet_bij_ons.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="download_supplier_not_found"
                )
    
    # ============================================
