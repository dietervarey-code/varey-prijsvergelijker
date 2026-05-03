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
        
        # ============================================
        # KOLOMNAMEN OPSCHONEN
        # ============================================
        
        # Verwijder BOM en andere onzichtbare karakters uit kolomnamen
        def clean_column_name(col):
            if col is None:
                return 'unnamed'
            col = str(col)
            # Verwijder BOM (Byte Order Mark)
            col = col.replace('\ufeff', '')
            # Verwijder andere onzichtbare karakters
            col = col.replace('\u200b', '')  # Zero-width space
            col = col.replace('\xa0', ' ')   # Non-breaking space -> normale spatie
            # Strip whitespace
            col = col.strip()
            return col if col else 'unnamed'
        
        df.columns = [clean_column_name(c) for c in df.columns]
        
        # Verwijder volledig lege rijen en kolommen
        df = df.dropna(how='all').dropna(axis=1, how='all')
        df = df.reset_index(drop=True)
        
        # ============================================
        # DUPLICATE KOLOMNAMEN OPLOSSEN IN BRON
        # ============================================
        
        # Als er duplicate kolomnamen zijn, maak ze uniek
        cols = df.columns.tolist()
        seen = {}
        new_cols = []
        for col in cols:
            if col in seen:
                seen[col] += 1
                new_cols.append(f"{col}_{seen[col]}")
            else:
                seen[col] = 0
                new_cols.append(col)
        df.columns = new_cols
        
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
            options=own_df.columns.tolist(),
            key="own_article"
        )
        own_price_col = st.selectbox(
            "Kolom met huidige prijs:",
            options=own_df.columns.tolist(),
            key="own_price"
        )
        
        # Extra kolommen: alle behalve artikel en prijs
        own_available_extra = [c for c in own_df.columns if c not in [own_article_col, own_price_col]]
        
        # Select All checkbox
        own_select_all = st.checkbox("Selecteer alle extra kolommen", key="own_select_all")
        
        if own_select_all:
            own_extra_cols = own_available_extra
            st.info(f"✅ {len(own_extra_cols)} kolommen geselecteerd")
        else:
            own_extra_cols = st.multiselect(
                "Extra kolommen meenemen (optioneel):",
                options=own_available_extra,
                default=[],
                key="own_extra"
            )
    
    with col2:
        st.subheader("Leverancier bestand")
        supplier_article_col = st.selectbox(
            "Kolom met artikelnummer/code:",
            options=supplier_df.columns.tolist(),
            key="supplier_article"
        )
        supplier_price_col = st.selectbox(
            "Kolom met nieuwe prijs:",
            options=supplier_df.columns.tolist(),
            key="supplier_price"
        )
        
        # Extra kolommen: alle behalve artikel en prijs
        supplier_available_extra = [c for c in supplier_df.columns if c not in [supplier_article_col, supplier_price_col]]
        
        # Select All checkbox
        supplier_select_all = st.checkbox("Selecteer alle extra kolommen", key="supplier_select_all")
        
        if supplier_select_all:
            supplier_extra_cols = supplier_available_extra
            st.info(f"✅ {len(supplier_extra_cols)} kolommen geselecteerd")
        else:
            supplier_extra_cols = st.multiselect(
                "Extra kolommen meenemen (optioneel):",
                options=supplier_available_extra,
                default=[],
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
            
            # Reset index om problemen te voorkomen
            result = result.reset_index(drop=True)
            
            # Bouw kolommenlijst expliciet op
            output_cols = [own_article_col] + own_extra_cols + [own_price_col]
            
            # Voeg leverancier prijs en extra kolommen toe
            # Let op: _supplier_price is de interne naam, we hernoemen later
            result_cols = output_cols + ['_supplier_price'] + supplier_extra_cols + ['Verschil €', 'Verschil %', 'Status']
            
            # Controleer of alle kolommen bestaan
            missing_cols = [c for c in result_cols if c not in result.columns]
            if missing_cols:
                st.error(f"Ontbrekende kolommen: {missing_cols}")
                st.stop()
            
            # Selecteer alleen de gewenste kolommen
            final_result = result[result_cols].copy()
            
            # Bouw nieuwe kolomnamen op - MOET EXACT EVENVEEL ZIJN
            # Hernoem berekende Status kolom naar iets unieks om conflicten te voorkomen
            new_col_names = (
                [own_article_col] +                    # Artikelnummer (behoud originele naam)
                own_extra_cols +                       # Extra kolommen eigen bestand
                ['Huidige prijs'] +                    # Eigen prijs hernoemd
                ['Nieuwe prijs'] +                     # Leverancier prijs hernoemd
                supplier_extra_cols +                  # Extra kolommen leverancier
                ['Verschil €', 'Verschil %', 'Prijsstatus']  # Berekende kolommen - hernoemd naar Prijsstatus
            )
            
            # ============================================
            # DUPLICATE KOLOMNAMEN OPLOSSEN
            # ============================================
            
            # Tel hoe vaak elke naam voorkomt en maak uniek
            seen = {}
            unique_col_names = []
            for name in new_col_names:
                if name in seen:
                    seen[name] += 1
                    unique_name = f"{name}_{seen[name]}"
                    unique_col_names.append(unique_name)
                else:
                    seen[name] = 0
                    unique_col_names.append(name)
            
            new_col_names = unique_col_names
            
            # Debug check
            if len(result_cols) != len(new_col_names):
                st.error(f"Kolom mismatch! result_cols: {len(result_cols)}, new_col_names: {len(new_col_names)}")
                st.write("result_cols:", result_cols)
                st.write("new_col_names:", new_col_names)
                st.stop()
            
            # Hernoem kolommen
            final_result.columns = new_col_names
            
            # Reset index nogmaals voor zekerheid
            final_result = final_result.reset_index(drop=True)
            
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
            supplier_not_found_export = supplier_not_found_export.reset_index(drop=True)
            st.session_state['supplier_not_found'] = supplier_not_found_export
            
            # Artikelen bij ons die NIET bij leverancier voorkomen
            own_not_found = result[result['_supplier_price'].isna()].copy()
            own_not_found_export_cols = [own_article_col] + own_extra_cols + [own_price_col]
            # Filter alleen bestaande kolommen (voor het geval van mismatch)
            own_not_found_export_cols = [c for c in own_not_found_export_cols if c in own_not_found.columns]
            own_not_found_export = own_not_found[own_not_found_export_cols].copy()
            own_not_found_export = own_not_found_export.reset_index(drop=True)
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
    
    # Bepaal welke kolom de prijsstatus is (kan 'Status' of 'Prijsstatus' zijn)
    status_col = 'Prijsstatus' if 'Prijsstatus' in final_result.columns else 'Status'
    
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
        display_df = final_result[final_result[status_col] == '🔴 Prijsverhoging'].copy()
    elif filter_option == "🟢 Alleen prijsverlagingen":
        display_df = final_result[final_result[status_col] == '🟢 Prijsverlaging'].copy()
    elif filter_option == "🔴🟢 Alle wijzigingen":
        display_df = final_result[final_result[status_col].isin(['🔴 Prijsverhoging', '🟢 Prijsverlaging'])].copy()
    elif filter_option == "⚠️ Niet gevonden":
        display_df = final_result[final_result[status_col] == '⚠️ Niet gevonden'].copy()
    else:
        display_df = final_result.copy()
    
    # Sorteer opties - gebruik dynamische status kolom
    sort_options = ['Verschil €', 'Verschil %', 'Huidige prijs', 'Nieuwe prijs', status_col]
    sort_col = st.selectbox(
        "Sorteer op:",
        options=sort_options,
        index=0
    )
    sort_order = st.radio("Volgorde:", ['Aflopend', 'Oplopend'], horizontal=True)
    
    display_df = display_df.sort_values(
        by=sort_col, 
        ascending=(sort_order == 'Oplopend'),
        na_position='last'
    )
    
    # Reset index na sortering
    display_df = display_df.reset_index(drop=True)
    
    # Toon aantal resultaten
    st.info(f"📋 {len(display_df)} artikelen gevonden met huidige filter")
    
    # ============================================
    # TABEL WEERGAVE
    # ============================================
    
    # Bouw column_config op
    col_config = {}
    
    # Prijs kolommen als nummer met euro formatting
    if 'Huidige prijs' in display_df.columns:
        col_config['Huidige prijs'] = st.column_config.NumberColumn(format="€ %.2f")
    if 'Nieuwe prijs' in display_df.columns:
        col_config['Nieuwe prijs'] = st.column_config.NumberColumn(format="€ %.2f")
    if 'Verschil €' in display_df.columns:
        col_config['Verschil €'] = st.column_config.NumberColumn(format="€ %.2f")
    if 'Verschil %' in display_df.columns:
        col_config['Verschil %'] = st.column_config.NumberColumn(format="%.2f %%")
    
    # Alle andere kolommen als tekst (voorkomt wetenschappelijke notatie etc.)
    for col in display_df.columns:
        if col not in col_config:
            col_config[col] = st.column_config.TextColumn(col)
    
    # Toon dataframe ZONDER index
    st.dataframe(
        display_df,
        use_container_width=True,
        height=400,
        column_config=col_config,
        hide_index=True
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
        changes_only = final_result[final_result[status_col].isin(['🔴 Prijsverhoging', '🟢 Prijsverlaging'])]
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
                    st.dataframe(
                        own_not_found.head(20), 
                        use_container_width=True,
                        hide_index=True
                    )
                
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
                    st.dataframe(
                        supplier_not_found.head(20), 
                        use_container_width=True,
                        hide_index=True
                    )
                
                st.download_button(
                    label="📥 Export: Leverancier artikelen NIET bij ons",
                    data=convert_to_excel(supplier_not_found),
                    file_name="leverancier_artikelen_niet_bij_ons.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="download_supplier_not_found"
                )

    # ============================================
    # STAP 4: PUSH NAAR PRIORITY
    # ============================================
    st.divider()
    st.header("🚀 Stap 4: Push naar Priority ERP")
    
    # Check of er data is om te pushen
    if 'final_result' not in st.session_state:
        st.warning("⚠️ Voer eerst een prijsvergelijking uit.")
        st.stop()
    
    final_result = st.session_state['final_result']
    status_col = 'Prijsstatus' if 'Prijsstatus' in final_result.columns else 'Status'
    
    # ============================================
    # 4.1 KOLOM MAPPING
    # ============================================
    st.subheader("📋 Kolom Mapping")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Artikelnummer kolom selectie (voor PARTNAME in Priority)
        partname_candidates = [c for c in final_result.columns if any(x in c.lower() for x in ['article', 'artikel', 'partname', 'part_name', 'artikelnummer', 'article_code', 'code'])]
        default_partname = partname_candidates[0] if partname_candidates else final_result.columns[0]
        
        partname_col = st.selectbox(
            "Kolom met artikelnummer (→ PARTNAME):",
            options=final_result.columns.tolist(),
            index=final_result.columns.tolist().index(default_partname) if default_partname in final_result.columns else 0,
            key="partname_col",
            help="Deze kolom moet overeenkomen met PARTNAME in LOGPART"
        )
    
    with col2:
        # Nieuwe prijs kolom selectie
        price_candidates = [c for c in final_result.columns if 'prijs' in c.lower() or 'price' in c.lower()]
        default_price = 'Nieuwe prijs' if 'Nieuwe prijs' in final_result.columns else (price_candidates[0] if price_candidates else final_result.columns[0])
        
        new_price_col = st.selectbox(
            "Kolom met nieuwe prijs (→ BASEPLPRICE):",
            options=final_result.columns.tolist(),
            index=final_result.columns.tolist().index(default_price) if default_price in final_result.columns else 0,
            key="new_price_col",
            help="Deze waarde wordt naar BASEPLPRICE gestuurd"
        )
    
    # Extra kolommen voor preview
    available_preview_cols = [c for c in final_result.columns if c not in [partname_col, new_price_col, status_col]]
    
    # Suggesties voor extra kolommen (artikelnaam, code, etc.)
    suggested_cols = [c for c in available_preview_cols if any(x in c.lower() for x in ['name', 'naam', 'article', 'artikel', 'supplier', 'leverancier', 'omschrijving', 'description', 'huidige', 'current'])]
    default_extra_cols = suggested_cols[:3] if suggested_cols else available_preview_cols[:3]
    
    extra_preview_cols = st.multiselect(
        "Extra kolommen tonen in preview (optioneel):",
        options=available_preview_cols,
        default=default_extra_cols,
        key="extra_preview_cols",
        help="Selecteer extra kolommen om te tonen in de preview tabel"
    )
    
    # ============================================
    # 4.2 FILTER SELECTIE
    # ============================================
    st.subheader("📊 Welke artikelen pushen?")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        include_increases = st.checkbox("🔴 Prijsverhogingen", value=True, key="include_increases")
    with col2:
        include_decreases = st.checkbox("🟢 Prijsverlagingen", value=True, key="include_decreases")
    with col3:
        include_unchanged = st.checkbox("⚪ Ongewijzigd", value=False, key="include_unchanged")
    
    # Filter data op basis van selectie
    selected_statuses = []
    if include_increases:
        selected_statuses.append('🔴 Prijsverhoging')
    if include_decreases:
        selected_statuses.append('🟢 Prijsverlaging')
    if include_unchanged:
        selected_statuses.append('⚪ Ongewijzigd')
    
    if not selected_statuses:
        st.warning("⚠️ Selecteer minimaal één categorie om te pushen.")
        st.stop()
    
    # Filter op status EN artikelnummer moet gevuld zijn
    push_df = final_result[
        (final_result[status_col].isin(selected_statuses)) &
        (final_result[partname_col].notna()) &
        (final_result[partname_col].astype(str).str.strip() != '') &
        (final_result[partname_col].astype(str).str.lower() != 'nan')
    ].copy()
    
    st.info(f"📋 {len(push_df)} artikelen geselecteerd met geldig artikelnummer")
    
    if len(push_df) == 0:
        st.warning("⚠️ Geen artikelen gevonden met geldig artikelnummer in de geselecteerde categorieën.")
        st.stop()
    
    # ============================================
    # 4.3 MARK-UP OPTIES
    # ============================================
    st.subheader("💰 Prijsaanpassing (Mark-up)")
    
    markup_type = st.radio(
        "Mark-up type:",
        options=["Geen mark-up", "Percentage (%)", "Vast bedrag (€)"],
        horizontal=True,
        key="markup_type"
    )
    
    # Initialiseer variabelen
    markup_value = 0
    markup_scope = "Alle artikelen"
    group_markups = {}
    group_col = None
    selected_for_markup = []
    
    # Mark-up waarde en scope
    if markup_type != "Geen mark-up":
        col1, col2 = st.columns(2)
        
        with col1:
            if markup_type == "Percentage (%)":
                markup_value = st.number_input(
                    "Mark-up percentage:",
                    min_value=0.0,
                    max_value=100.0,
                    value=5.0,
                    step=0.5,
                    key="markup_pct",
                    help="Bv. 5 voor 5% verhoging"
                )
            else:
                markup_value = st.number_input(
                    "Mark-up bedrag (€):",
                    min_value=0.0,
                    value=10.0,
                    step=1.0,
                    key="markup_fixed",
                    help="Vast bedrag dat wordt opgeteld"
                )
        
        with col2:
            markup_scope = st.radio(
                "Toepassen op:",
                options=["Alle artikelen", "Per artikelgroep", "Handmatig selecteren"],
                key="markup_scope"
            )
        
        # Per artikelgroep configuratie
        if markup_scope == "Per artikelgroep":
            # Selecteer groepkolom
            group_col_candidates = [c for c in final_result.columns if any(x in c.lower() for x in ['group', 'family', 'categor', 'groep', 'familie'])]
            
            group_col = st.selectbox(
                "Groepeer op kolom:",
                options=final_result.columns.tolist(),
                index=final_result.columns.tolist().index(group_col_candidates[0]) if group_col_candidates else 0,
                key="group_col"
            )
            
            # Toon unieke groepen met mark-up input
            unique_groups = push_df[group_col].dropna().unique()
            
            if len(unique_groups) > 0 and len(unique_groups) <= 50:
                st.write("**Mark-up per groep:**")
                
                # Maak 3 kolommen voor compactere weergave
                cols = st.columns(3)
                for idx, group in enumerate(sorted(unique_groups)):
                    with cols[idx % 3]:
                        if markup_type == "Percentage (%)":
                            group_markups[group] = st.number_input(
                                f"{group}",
                                min_value=0.0,
                                max_value=100.0,
                                value=float(markup_value),
                                step=0.5,
                                key=f"group_markup_{idx}",
                                label_visibility="visible"
                            )
                        else:
                            group_markups[group] = st.number_input(
                                f"{group}",
                                min_value=0.0,
                                value=float(markup_value),
                                step=1.0,
                                key=f"group_markup_{idx}",
                                label_visibility="visible"
                            )
            elif len(unique_groups) > 50:
                st.warning(f"⚠️ Te veel groepen ({len(unique_groups)}). Gebruik 'Alle artikelen' of 'Handmatig selecteren'.")
                markup_scope = "Alle artikelen"
        
        # Handmatige selectie
        if markup_scope == "Handmatig selecteren":
            st.write("**Selecteer artikelen voor mark-up:**")
            
            # Voeg selectie kolom toe
            markup_selection_df = push_df[[partname_col, new_price_col, status_col]].copy()
            markup_selection_df['_apply_markup'] = False
            
            edited_df = st.data_editor(
                markup_selection_df.head(100),
                column_config={
                    "_apply_markup": st.column_config.CheckboxColumn(
                        "Mark-up?",
                        help="Vink aan om mark-up toe te passen",
                        default=False
                    )
                },
                disabled=[partname_col, new_price_col, status_col],
                hide_index=True,
                key="markup_selection"
            )
            
            # Update selecties
            selected_for_markup = edited_df[edited_df['_apply_markup'] == True][partname_col].tolist()
            st.info(f"✅ {len(selected_for_markup)} artikelen geselecteerd voor mark-up")
    
    # ============================================
    # 4.4 BEREKEN FINALE PRIJZEN
    # ============================================
    
    def calculate_final_price(row):
        """Bereken finale prijs inclusief eventuele mark-up"""
        try:
            price_val = str(row[new_price_col]).replace(',', '.').replace('€', '').replace(' ', '').strip()
            base_price = float(price_val)
        except (ValueError, TypeError):
            return None
        
        if markup_type == "Geen mark-up":
            return round(base_price, 2)
        
        # Bepaal mark-up voor dit artikel
        applied_markup = 0
        if markup_scope == "Alle artikelen":
            applied_markup = markup_value
        elif markup_scope == "Per artikelgroep" and group_col:
            group = row.get(group_col, None)
            applied_markup = group_markups.get(group, 0)
        elif markup_scope == "Handmatig selecteren":
            if row[partname_col] in selected_for_markup:
                applied_markup = markup_value
            else:
                applied_markup = 0
        
        # Bereken finale prijs
        if markup_type == "Percentage (%)":
            final_price = base_price * (1 + applied_markup / 100)
        else:  # Vast bedrag
            final_price = base_price + applied_markup
        
        return round(final_price, 2)
    
    # Bereken finale prijzen
    push_df['_final_price'] = push_df.apply(calculate_final_price, axis=1)
    
    # Verwijder rijen zonder geldige prijs
    push_df = push_df[push_df['_final_price'].notna()].copy()
    
    if len(push_df) == 0:
        st.warning("⚠️ Geen artikelen met geldige prijzen gevonden.")
        st.stop()
    
    # ============================================
    # 4.5 PREVIEW
    # ============================================
    st.subheader("👁️ Preview")
    
    # Bouw preview kolommen op
    preview_cols = [partname_col]
    
    # Voeg extra kolommen toe
    for col in extra_preview_cols:
        if col in push_df.columns and col not in preview_cols:
            preview_cols.append(col)
    
    # Voeg prijs kolommen toe
    preview_cols.append(new_price_col)
    if markup_type != "Geen mark-up":
        preview_cols.append('_final_price')
    preview_cols.append(status_col)
    
    # Maak preview DataFrame
    preview_df = push_df[preview_cols].copy()
    
    # Hernoem _final_price voor duidelijkheid
    if '_final_price' in preview_df.columns:
        preview_df = preview_df.rename(columns={'_final_price': 'Finale prijs'})
    
    # Column config voor formatting
    preview_col_config = {
        'Finale prijs': st.column_config.NumberColumn(format="€ %.2f"),
    }
    if 'prijs' in new_price_col.lower() or 'price' in new_price_col.lower():
        preview_col_config[new_price_col] = st.column_config.NumberColumn(format="€ %.2f")
    
    st.dataframe(
        preview_df.head(50),
        use_container_width=True,
        hide_index=True,
        column_config=preview_col_config
    )
    
    if len(push_df) > 50:
        st.caption(f"... en {len(push_df) - 50} meer artikelen")
    
    # Samenvatting
    col1, col2, col3 = st.columns(3)
    col1.metric("Totaal te pushen", len(push_df))
    col2.metric("Gemiddelde finale prijs", f"€{push_df['_final_price'].mean():.2f}")
    col3.metric("Totale waarde", f"€{push_df['_final_price'].sum():,.2f}")
    
    # ============================================
    # 4.6 PUSH NAAR PRIORITY
    # ============================================
    st.divider()
    
    # Priority API configuratie
    PRIORITY_BASE = "https://p.priority-connect.online/odata/Priority/tabCA637.ini/vareydb/"
    PRIORITY_AUTH = "Basic Q0E5RTFDNTgxNEJENDNEMEI3RDlBNTI1RDFCOThGQ0Y6UEFU"
    BATCH_SIZE = 200
    
    # Push knop
    col1, col2 = st.columns([3, 1])
    
    with col1:
        push_button = st.button(
            f"🚀 Push {len(push_df)} artikelen naar Priority",
            type="primary",
            use_container_width=True,
            key="push_to_priority"
        )
    
    with col2:
        dry_run = st.checkbox("🧪 Test mode", value=True, help="Simuleert push zonder echte API calls")
    
    if push_button:
        import requests
        import time
        
        # Resultaten bijhouden
        results = []
        success_count = 0
        error_count = 0
        
        # Progress bar
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Verwerk artikelen
        total_items = len(push_df)
        
        for idx, (_, row) in enumerate(push_df.iterrows()):
            partname = str(row[partname_col]).strip()
            final_price = row['_final_price']
            
            # Update progress
            progress = (idx + 1) / total_items
            progress_bar.progress(progress)
            status_text.text(f"⏳ Verwerken: {idx + 1}/{total_items} - Artikel {partname}")
            
            if dry_run:
                # Simuleer succes in test mode
                results.append({
                    'partname': partname,
                    'new_price': final_price,
                    'status': '✅ Succes (test mode)',
                    'error': None
                })
                success_count += 1
                time.sleep(0.01)  # Kleine delay voor visuele feedback
            else:
                # Echte API call
                try:
                    # URL encode de PARTNAME voor veilige request
                    import urllib.parse
                    encoded_partname = urllib.parse.quote(partname, safe='')
                    
                    url = f"{PRIORITY_BASE}LOGPART(PARTNAME='{encoded_partname}')"
                    headers = {
                        'Authorization': PRIORITY_AUTH,
                        'Content-Type': 'application/json'
                    }
                    payload = {
                        'BASEPLPRICE': final_price
                    }
                    
                    response = requests.patch(url, json=payload, headers=headers, timeout=30)
                    
                    if response.status_code in [200, 204]:
                        results.append({
                            'partname': partname,
                            'new_price': final_price,
                            'status': '✅ Succes',
                            'error': None
                        })
                        success_count += 1
                    else:
                        error_msg = f"HTTP {response.status_code}"
                        try:
                            error_detail = response.json()
                            if 'error' in error_detail:
                                error_msg = error_detail['error'].get('message', error_msg)
                        except:
                            error_msg = response.text[:200] if response.text else error_msg
                        
                        results.append({
                            'partname': partname,
                            'new_price': final_price,
                            'status': '❌ Mislukt',
                            'error': error_msg
                        })
                        error_count += 1
                
                except requests.exceptions.Timeout:
                    results.append({
                        'partname': partname,
                        'new_price': final_price,
                        'status': '❌ Timeout',
                        'error': 'Request timeout na 30 seconden'
                    })
                    error_count += 1
                
                except requests.exceptions.RequestException as e:
                    results.append({
                        'partname': partname,
                        'new_price': final_price,
                        'status': '❌ Fout',
                        'error': str(e)
                    })
                    error_count += 1
                
                # Kleine delay om API niet te overbelasten
                if (idx + 1) % BATCH_SIZE == 0:
                    time.sleep(0.5)  # Halve seconde pauze per batch
        
        # Verwijder progress indicators
        progress_bar.empty()
        status_text.empty()
        
        # ============================================
        # 4.7 RESULTATEN TONEN
        # ============================================
        st.subheader("📊 Push Resultaten")
        
        # Samenvatting
        col1, col2, col3 = st.columns(3)
        col1.metric("✅ Succesvol", success_count)
        col2.metric("❌ Mislukt", error_count)
        col3.metric("📊 Totaal", len(results))
        
        # Resultaten DataFrame
        results_df = pd.DataFrame(results)
        
        # Sla resultaten op in session state voor retry
        # Gebruik _for_retry suffix om conflict met widget keys te voorkomen
        st.session_state['push_results'] = results_df
        st.session_state['push_df_for_retry'] = push_df.copy()
        st.session_state['partname_col_for_retry'] = partname_col
        
        # Toon resultaten tabel
        if error_count > 0:
            st.warning(f"⚠️ {error_count} artikelen zijn niet bijgewerkt. Zie details hieronder.")
            
            # Toon gefaalde items
            failed_df = results_df[results_df['status'].str.contains('❌')]
            st.write("**Mislukte updates:**")
            st.dataframe(
                failed_df,
                use_container_width=True,
                hide_index=True
            )
        else:
            st.success(f"🎉 Alle {success_count} artikelen succesvol bijgewerkt!")
        
        # Toon volledige resultaten
        with st.expander("📋 Bekijk alle resultaten"):
            st.dataframe(
                results_df,
                use_container_width=True,
                hide_index=True
            )
        
        # Download resultaten
        st.download_button(
            label="📥 Download resultaten (Excel)",
            data=convert_to_excel(results_df),
            file_name="priority_push_resultaten.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="download_push_results"
        )
    
    # ============================================
    # 4.8 RETRY MISLUKTE ITEMS
    # ============================================
    if 'push_results' in st.session_state:
        results_df = st.session_state['push_results']
        failed_items = results_df[results_df['status'].str.contains('❌')]
        
        if len(failed_items) > 0:
            st.divider()
            st.subheader("🔄 Opnieuw proberen")
            
            st.write(f"**{len(failed_items)} artikelen** zijn niet bijgewerkt.")
            
            # Toon gefaalde items
            with st.expander("👀 Bekijk mislukte items"):
                st.dataframe(
                    failed_items,
                    use_container_width=True,
                    hide_index=True
                )
            
            col1, col2 = st.columns([3, 1])
            
            with col1:
                retry_button = st.button(
                    f"🔄 Retry {len(failed_items)} mislukte items",
                    type="secondary",
                    use_container_width=True,
                    key="retry_failed"
                )
            
            with col2:
                retry_dry_run = st.checkbox("🧪 Test mode", value=True, key="retry_dry_run")
            
            if retry_button:
                import requests
                import urllib.parse
                import time
                
                # Haal originele data op (gebruik _for_retry keys)
                retry_push_df = st.session_state['push_df_for_retry']
                retry_partname_col = st.session_state['partname_col_for_retry']
                
                # Filter alleen mislukte items
                failed_partnames = failed_items['partname'].astype(str).tolist()
                retry_df = retry_push_df[retry_push_df[retry_partname_col].astype(str).isin(failed_partnames)].copy()
                
                # Resultaten bijhouden
                retry_results = []
                retry_success = 0
                retry_error = 0
                
                # Progress bar
                retry_progress = st.progress(0)
                retry_status = st.empty()
                
                for idx, (_, row) in enumerate(retry_df.iterrows()):
                    partname = str(row[retry_partname_col]).strip()
                    final_price = row['_final_price']
                    
                    # Update progress
                    progress = (idx + 1) / len(retry_df)
                    retry_progress.progress(progress)
                    retry_status.text(f"🔄 Retry: {idx + 1}/{len(retry_df)} - Artikel {partname}")
                    
                    if retry_dry_run:
                        retry_results.append({
                            'partname': partname,
                            'new_price': final_price,
                            'status': '✅ Succes (test mode)',
                            'error': None
                        })
                        retry_success += 1
                        time.sleep(0.01)
                    else:
                        try:
                            encoded_partname = urllib.parse.quote(partname, safe='')
                            url = f"{PRIORITY_BASE}LOGPART(PARTNAME='{encoded_partname}')"
                            headers = {
                                'Authorization': PRIORITY_AUTH,
                                'Content-Type': 'application/json'
                            }
                            payload = {
                                'BASEPLPRICE': final_price
                            }
                            
                            response = requests.patch(url, json=payload, headers=headers, timeout=30)
                            
                            if response.status_code in [200, 204]:
                                retry_results.append({
                                    'partname': partname,
                                    'new_price': final_price,
                                    'status': '✅ Succes',
                                    'error': None
                                })
                                retry_success += 1
                            else:
                                error_msg = f"HTTP {response.status_code}"
                                try:
                                    error_detail = response.json()
                                    if 'error' in error_detail:
                                        error_msg = error_detail['error'].get('message', error_msg)
                                except:
                                    error_msg = response.text[:200] if response.text else error_msg
                                
                                retry_results.append({
                                    'partname': partname,
                                    'new_price': final_price,
                                    'status': '❌ Mislukt',
                                    'error': error_msg
                                })
                                retry_error += 1
                        
                        except Exception as e:
                            retry_results.append({
                                'partname': partname,
                                'new_price': final_price,
                                'status': '❌ Fout',
                                'error': str(e)
                            })
                            retry_error += 1
                        
                        time.sleep(0.1)  # Kleine delay
                
                # Verwijder progress
                retry_progress.empty()
                retry_status.empty()
                
                # Toon retry resultaten
                st.subheader("📊 Retry Resultaten")
                
                col1, col2 = st.columns(2)
                col1.metric("✅ Nu succesvol", retry_success)
                col2.metric("❌ Nog steeds mislukt", retry_error)
                
                retry_results_df = pd.DataFrame(retry_results)
                
                # Update session state met nieuwe resultaten
                original_success = results_df[~results_df['status'].str.contains('❌')]
                updated_results = pd.concat([original_success, retry_results_df], ignore_index=True)
                st.session_state['push_results'] = updated_results
                
                # Toon resultaten
                if retry_error > 0:
                    st.warning(f"⚠️ {retry_error} artikelen nog steeds niet bijgewerkt.")
                    st.dataframe(
                        retry_results_df[retry_results_df['status'].str.contains('❌')],
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.success("🎉 Alle retry items succesvol bijgewerkt!")
                
                # Download retry resultaten
                st.download_button(
                    label="📥 Download retry resultaten (Excel)",
                    data=convert_to_excel(retry_results_df),
                    file_name="priority_retry_resultaten.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="download_retry_results"
                )
    
    # ============================================
