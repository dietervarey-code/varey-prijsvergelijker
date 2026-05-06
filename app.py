import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

import requests
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

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
            sample = df[col].astype(str).head(2000)
            max_length = max(sample.map(len).max(), len(col)) + 2
            worksheet.set_column(i, i, min(max_length, 30))
    
    return output.getvalue()

def convert_to_csv(df):
    """Converteer DataFrame naar CSV voor download"""
    return df.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')

def unique_list(items):
    result = []

    for item in items:
        if item not in result:
            result.append(item)

    return result

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
            cond_not_found = result['_supplier_price'].isna()
            cond_up = result['Verschil €'] > 0.01
            cond_down = result['Verschil €'] < -0.01

            result['Status'] = np.select(
                [cond_not_found, cond_up, cond_down],
                ['⚠️ Niet gevonden', '🔴 Prijsverhoging', '🟢 Prijsverlaging'],
                default='⚪ Ongewijzigd'
            )
            
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
            own_not_found = result[result['_supplier_price'].isna()].copy()
            own_not_found_export_cols = [own_article_col] + own_extra_cols + [own_price_col]
            own_not_found_export_cols = [c for c in own_not_found_export_cols if c in own_not_found.columns]
            own_not_found_export = own_not_found[own_not_found_export_cols].copy()
            own_not_found_export = own_not_found_export.reset_index(drop=True)
            MAX_STORE_ROWS = 50000
            if len(final_result) <= MAX_STORE_ROWS:
                st.session_state['supplier_not_found'] = supplier_not_found_export
                st.session_state['own_not_found'] = own_not_found_export
            else:
                st.session_state['supplier_not_found'] = None
                st.session_state['own_not_found'] = None
                st.warning("⚠️ Grote dataset: 'niet-gematchte artikelen' lijsten worden niet in geheugen bewaard om memory te sparen. Gebruik vooral exports van het hoofdresultaat.")

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
    MAX_PREVIEW_ROWS = 2000
    st.caption(f"Toont eerste {min(MAX_PREVIEW_ROWS, len(display_df))} rijen (performance).")
    st.dataframe(
        display_df.head(MAX_PREVIEW_ROWS),
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
        own_not_found = st.session_state.get('own_not_found')
        if own_not_found is None:
            st.info("Niet-gematchte lijst niet beschikbaar (dataset te groot).")
        else:
            st.metric("Onze artikelen niet bij leverancier", len(own_not_found))

            if len(own_not_found) > 0:
                with st.expander("👀 Bekijk lijst"):
                    st.dataframe(own_not_found.head(20), use_container_width=True, hide_index=True)

                st.download_button(
                    label="📥 Export: Onze artikelen NIET bij leverancier",
                    data=convert_to_excel(own_not_found),
                    file_name="onze_artikelen_niet_bij_leverancier.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="download_own_not_found"
                )
    
    with col2:
        supplier_not_found = st.session_state.get('supplier_not_found')

        if supplier_not_found is None:
            st.info("Niet-gematchte lijst niet beschikbaar (dataset te groot).")
        else:
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
        partname_candidates = [
            c for c in final_result.columns
            if any(x in c.lower() for x in ['partname', 'artikelnummer', 'article_code', 'article', 'artikel', 'code'])
        ]
        default_partname = partname_candidates[0] if partname_candidates else final_result.columns[0]

        partname_col = st.selectbox(
            "Kolom met artikelnummer (→ PARTNAME):",
            options=final_result.columns.tolist(),
            index=final_result.columns.tolist().index(default_partname) if default_partname in final_result.columns else 0,
            key="partname_col",
            help="Deze kolom moet overeenkomen met PARTNAME in LOGPART"
        )

    with col2:
        price_candidates = [c for c in final_result.columns if 'prijs' in c.lower() or 'price' in c.lower()]
        default_price = 'Nieuwe prijs' if 'Nieuwe prijs' in final_result.columns else (price_candidates[0] if price_candidates else final_result.columns[0])

        new_price_col = st.selectbox(
            "Kolom met nieuwe prijs (→ BASEPLPRICE):",
            options=final_result.columns.tolist(),
            index=final_result.columns.tolist().index(default_price) if default_price in final_result.columns else 0,
            key="new_price_col",
            help="Deze waarde wordt naar BASEPLPRICE gestuurd"
        )

    # Priority ID (moet gevuld zijn om te patchen)
    priority_id_candidates = [c for c in final_result.columns if c.lower() == "priority_id" or "priority" in c.lower()]
    default_priority_id = "priority_id" if "priority_id" in final_result.columns else (priority_id_candidates[0] if priority_id_candidates else final_result.columns[0])

    priority_id_col = st.selectbox(
        "Kolom met Priority ID (verplicht om te patchen):",
        options=final_result.columns.tolist(),
        index=final_result.columns.tolist().index(default_priority_id) if default_priority_id in final_result.columns else 0,
        key="priority_id_col_push",
        help="Alleen rijen met een ingevulde Priority ID worden naar Priority gestuurd."
    )

    # Extra kolommen voor preview
    available_preview_cols = [c for c in final_result.columns if c not in [partname_col, new_price_col, priority_id_col, status_col]]
    suggested_cols = [c for c in available_preview_cols if any(x in c.lower() for x in ['name', 'naam', 'supplier', 'leverancier', 'omschrijving', 'description', 'huidige', 'current'])]
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

    # Filter: status + partname aanwezig + priority_id aanwezig
    push_df = final_result[
        (final_result[status_col].isin(selected_statuses)) &
        (final_result[partname_col].notna()) &
        (final_result[partname_col].astype(str).str.strip() != '') &
        (final_result[partname_col].astype(str).str.lower() != 'nan') &
        (final_result[priority_id_col].notna()) &
        (final_result[priority_id_col].astype(str).str.strip() != '') &
        (final_result[priority_id_col].astype(str).str.lower() != 'nan')
    ].copy()

    st.info(f"📋 {len(push_df)} artikelen geselecteerd met geldig artikelnummer én Priority ID")

    if len(push_df) == 0:
        st.warning("⚠️ Geen artikelen gevonden met geldige Priority ID in de geselecteerde categorieën.")
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

    markup_value = 0
    markup_scope = "Alle artikelen"
    group_markups = {}
    group_col = None
    selected_for_markup = []

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
                )
            else:
                markup_value = st.number_input(
                    "Mark-up bedrag (€):",
                    min_value=0.0,
                    value=10.0,
                    step=1.0,
                    key="markup_fixed",
                )

        with col2:
            markup_scope = st.radio(
                "Toepassen op:",
                options=["Alle artikelen", "Per artikelgroep", "Handmatig selecteren"],
                key="markup_scope"
            )

        if markup_scope == "Per artikelgroep":
            group_col_candidates = [c for c in final_result.columns if any(x in c.lower() for x in ['group', 'family', 'categor', 'groep', 'familie'])]
            group_col = st.selectbox(
                "Groepeer op kolom:",
                options=final_result.columns.tolist(),
                index=final_result.columns.tolist().index(group_col_candidates[0]) if group_col_candidates else 0,
                key="group_col"
            )

            unique_groups = push_df[group_col].dropna().unique()
            if len(unique_groups) > 0 and len(unique_groups) <= 50:
                st.write("**Mark-up per groep:**")
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
                            )
                        else:
                            group_markups[group] = st.number_input(
                                f"{group}",
                                min_value=0.0,
                                value=float(markup_value),
                                step=1.0,
                                key=f"group_markup_{idx}",
                            )
            elif len(unique_groups) > 50:
                st.warning(f"⚠️ Te veel groepen ({len(unique_groups)}). Gebruik 'Alle artikelen' of 'Handmatig selecteren'.")
                markup_scope = "Alle artikelen"

        if markup_scope == "Handmatig selecteren":
            st.write("**Selecteer artikelen voor mark-up:**")
            selection_df = push_df[[partname_col, new_price_col, status_col]].copy()
            selection_df['_apply_markup'] = False

            edited_df = st.data_editor(
                selection_df.head(100),
                column_config={
                    "_apply_markup": st.column_config.CheckboxColumn("Mark-up?", default=False)
                },
                disabled=[partname_col, new_price_col, status_col],
                hide_index=True,
                key="markup_selection"
            )
            selected_for_markup = edited_df[edited_df['_apply_markup'] == True][partname_col].tolist()
            st.info(f"✅ {len(selected_for_markup)} artikelen geselecteerd voor mark-up")

    # ============================================
    # 4.4 BEREKEN FINALE PRIJZEN
    # ============================================
    def calculate_final_price(row):
        try:
            base_price = float(str(row[new_price_col]).replace(',', '.').replace('€', '').replace(' ', '').strip())
        except (ValueError, TypeError):
            return None

        if markup_type == "Geen mark-up":
            return round(base_price, 2)

        applied_markup = 0
        if markup_scope == "Alle artikelen":
            applied_markup = markup_value
        elif markup_scope == "Per artikelgroep" and group_col:
            applied_markup = group_markups.get(row.get(group_col, None), 0)
        elif markup_scope == "Handmatig selecteren":
            applied_markup = markup_value if row[partname_col] in selected_for_markup else 0

        if markup_type == "Percentage (%)":
            return round(base_price * (1 + applied_markup / 100), 2)
        else:
            return round(base_price + applied_markup, 2)

    push_df['_final_price'] = push_df.apply(calculate_final_price, axis=1)
    push_df = push_df[push_df['_final_price'].notna()].copy()

    if len(push_df) == 0:
        st.warning("⚠️ Geen artikelen met geldige prijzen gevonden.")
        st.stop()

    # ============================================
    # 4.5 PREVIEW
    # ============================================
    st.subheader("👁️ Preview")

    preview_cols = [priority_id_col, partname_col]

    for col in extra_preview_cols:
        if col in push_df.columns:
            preview_cols.append(col)

    preview_cols += [new_price_col, '_final_price', status_col]

    preview_cols = unique_list(preview_cols)

    preview_df = push_df[preview_cols].copy()
    preview_df = preview_df.rename(columns={'_final_price': 'Finale prijs'})

    st.dataframe(
        preview_df.head(50),
        use_container_width=True,
        hide_index=True,
        column_config={
            'Finale prijs': st.column_config.NumberColumn(format="€ %.2f")
        }
    )

    if len(push_df) > 50:
        st.caption(f"... en {len(push_df) - 50} meer artikelen")

    col1, col2, col3 = st.columns(3)
    col1.metric("Totaal te pushen", len(push_df))
    col2.metric("Gemiddelde finale prijs", f"€{push_df['_final_price'].mean():.2f}")
    col3.metric("Totale waarde", f"€{push_df['_final_price'].sum():,.2f}")

    # ============================================
    # 4.6 PUSH NAAR PRIORITY
    # ============================================
    st.divider()

    PRIORITY_BASE = "https://p.priority-connect.online/odata/Priority/tabCA637.ini/vareydb/"
    PRIORITY_AUTH = "Basic Q0E5RTFDNTgxNEJENDNEMEI3RDlBNTI1RDFCOThGQ0Y6UEFU"

    col1, col2 = st.columns([3, 1])
    with col1:
        push_button = st.button(
            f"🚀 Push {len(push_df)} artikelen naar Priority",
            type="primary",
            use_container_width=True,
            key="push_to_priority"
        )
    with col2:
        dry_run = st.checkbox("🧪 Test mode", value=False, key="dry_run_priority")

    if push_button:
        # ------------------------------------------------------------
        # PARALLEL PUSH (batches van 500) + retries + session reuse
        # ------------------------------------------------------------
        import requests
        import time
        import urllib.parse
        from concurrent.futures import ThreadPoolExecutor, as_completed

        BATCH_SIZE = 500
        MAX_WORKERS = st.number_input(
            "Parallel workers",
            min_value=1,
            max_value=16,
            value=6,
            step=1,
            help="Verlaag bij 429/504, verhoog als het stabiel blijft."
        )
        MAX_RETRIES = 3
        REQUEST_TIMEOUT = 60
        SLEEP_BETWEEN_BATCHES = 0.5

        # Resultaten
        results = []
        success_count = 0
        error_count = 0

        progress_bar = st.progress(0)
        status_text = st.empty()

        # Maak 1 herbruikbare session
        session = requests.Session()
        session.headers.update({
            "Authorization": PRIORITY_AUTH,
            "Content-Type": "application/json"
        })

        def priority_patch_one(partname: str, final_price: float):
            encoded_partname = urllib.parse.quote(str(partname).strip(), safe='')
            url = f"{PRIORITY_BASE}LOGPART(PARTNAME='{encoded_partname}')"
            payload = {"BASEPLPRICE": float(final_price)}

            last_error = None

            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    resp = session.patch(url, json=payload, timeout=REQUEST_TIMEOUT)

                    if resp.status_code in (200, 204):
                        return {
                            "partname": partname,
                            "new_price": float(final_price),
                            "status": "✅ Succes",
                            "http_status": resp.status_code,
                            "error": None
                        }

                    # retry op throttling / server errors
                    if resp.status_code in (429, 500, 502, 503, 504):
                        try:
                            j = resp.json()
                            last_error = j.get("error", {}).get("message") or j.get("message") or (resp.text[:200] if resp.text else f"HTTP {resp.status_code}")
                        except:
                            last_error = resp.text[:200] if resp.text else f"HTTP {resp.status_code}"

                        time.sleep((2 ** (attempt - 1)) + 0.1)
                        continue

                    # niet-retryable
                    try:
                        j = resp.json()
                        err = j.get("error", {}).get("message") or j.get("message") or (resp.text[:200] if resp.text else f"HTTP {resp.status_code}")
                    except:
                        err = resp.text[:200] if resp.text else f"HTTP {resp.status_code}"

                    return {
                        "partname": partname,
                        "new_price": float(final_price),
                        "status": "❌ Mislukt",
                        "http_status": resp.status_code,
                        "error": err
                    }

                except requests.exceptions.Timeout:
                    last_error = "Timeout"
                    time.sleep((2 ** (attempt - 1)) + 0.1)
                    continue
                except requests.exceptions.RequestException as e:
                    last_error = str(e)
                    time.sleep((2 ** (attempt - 1)) + 0.1)
                    continue

            return {
                "partname": partname,
                "new_price": float(final_price),
                "status": "❌ Mislukt (retries)",
                "http_status": None,
                "error": last_error
            }

        # Data klaarzetten (sneller dan iterrows in threads)
        items = list(zip(
            push_df[partname_col].astype(str).tolist(),
            push_df["_final_price"].astype(float).tolist()
        ))
        total_items = len(items)

        def chunks(lst, n):
            for i in range(0, len(lst), n):
                yield lst[i:i + n]

        processed = 0

        if dry_run:
            for partname, final_price in items:
                results.append({
                    "partname": partname,
                    "new_price": float(final_price),
                    "status": "✅ Succes (test mode)",
                    "http_status": None,
                    "error": None
                })
            success_count = len(results)

        else:
            batch_idx = 0
            for batch in chunks(items, BATCH_SIZE):
                batch_idx += 1
                status_text.text(f"⏳ Batch {batch_idx} - {len(batch)} artikelen (parallel: {int(MAX_WORKERS)})")

                with ThreadPoolExecutor(max_workers=int(MAX_WORKERS)) as ex:
                    futures = [ex.submit(priority_patch_one, p, pr) for (p, pr) in batch]

                    for fut in as_completed(futures):
                        res = fut.result()
                        results.append(res)

                        processed += 1
                        if res["status"].startswith("✅"):
                            success_count += 1
                        else:
                            error_count += 1

                        progress_bar.progress(processed / total_items)

                        if processed % 100 == 0 or processed == total_items:
                            status_text.text(f"⏳ Verwerkt {processed}/{total_items} | ✅ {success_count} | ❌ {error_count}")

                time.sleep(SLEEP_BETWEEN_BATCHES)

        progress_bar.empty()
        status_text.empty()

        results_df = pd.DataFrame(results)
        st.session_state["push_results"] = results_df
        st.session_state["push_df_for_retry"] = push_df.copy()
        st.session_state["partname_col_for_retry"] = partname_col

        # Toon resultaten (1x)
        st.subheader("📊 Push Resultaten")
        c1, c2, c3 = st.columns(3)
        c1.metric("✅ Succesvol", success_count)
        c2.metric("❌ Mislukt", error_count)
        c3.metric("📊 Totaal", len(results))

        if error_count > 0:
            st.warning(f"⚠️ {error_count} artikelen zijn niet bijgewerkt.")
            failed_df = results_df[results_df["status"].str.contains("❌")]
            st.dataframe(failed_df.head(2000), use_container_width=True, hide_index=True)
        else:
            st.success(f"🎉 Alle {success_count} artikelen succesvol bijgewerkt!")

        with st.expander("📋 Bekijk alle resultaten"):
            st.dataframe(results_df.head(5000), use_container_width=True, hide_index=True)
            st.caption("Toont max 5000 rijen voor performance.")

        st.download_button(
            label="📥 Download resultaten (Excel)",
            data=convert_to_excel(results_df),
            file_name="priority_push_resultaten.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="download_push_results_main"
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
                retry_dry_run = st.checkbox("🧪 Test mode", value=False, key="retry_dry_run")
            
            if retry_button:
                import requests
                import time
                import urllib.parse
                from concurrent.futures import ThreadPoolExecutor, as_completed

                # Settings retry
                RETRY_BATCH_SIZE = 500
                RETRY_MAX_WORKERS = 6
                RETRY_MAX_RETRIES = 3
                RETRY_TIMEOUT = 60
                RETRY_SLEEP_BETWEEN_BATCHES = 0.5

                retry_push_df = st.session_state['push_df_for_retry']
                retry_partname_col = st.session_state['partname_col_for_retry']

                failed_partnames = failed_items['partname'].astype(str).tolist()
                retry_df = retry_push_df[retry_push_df[retry_partname_col].astype(str).isin(failed_partnames)].copy()

                # Maak 1 session
                session = requests.Session()
                session.headers.update({
                    "Authorization": PRIORITY_AUTH,
                    "Content-Type": "application/json"
                })

                def retry_one(partname: str, final_price: float):
                    encoded_partname = urllib.parse.quote(str(partname).strip(), safe='')
                    url = f"{PRIORITY_BASE}LOGPART(PARTNAME='{encoded_partname}')"
                    payload = {"BASEPLPRICE": float(final_price)}

                    last_error = None

                    for attempt in range(1, RETRY_MAX_RETRIES + 1):
                        try:
                            resp = session.patch(url, json=payload, timeout=RETRY_TIMEOUT)
                            if resp.status_code in (200, 204):
                                return {"partname": partname, "new_price": float(final_price), "status": "✅ Succes", "error": None}
                            if resp.status_code in (429, 500, 502, 503, 504):
                                last_error = resp.text[:200] if resp.text else f"HTTP {resp.status_code}"
                                time.sleep((2 ** (attempt - 1)) + 0.1)
                                continue
                            return {"partname": partname, "new_price": float(final_price), "status": "❌ Mislukt", "error": resp.text[:200]}
                        except requests.exceptions.Timeout:
                            last_error = "Timeout"
                            time.sleep((2 ** (attempt - 1)) + 0.1)
                            continue
                        except requests.exceptions.RequestException as e:
                            last_error = str(e)
                            time.sleep((2 ** (attempt - 1)) + 0.1)
                            continue

                    return {"partname": partname, "new_price": float(final_price), "status": "❌ Mislukt (retries)", "error": last_error}

                # Prepare items
                items = list(zip(
                    retry_df[retry_partname_col].astype(str).tolist(),
                    retry_df["_final_price"].astype(float).tolist()
                ))
                total = len(items)

                retry_results = []
                retry_success = 0
                retry_error = 0

                retry_progress = st.progress(0)
                retry_status = st.empty()

                def chunks(lst, n):
                    for i in range(0, len(lst), n):
                        yield lst[i:i+n]

                for batch_idx, batch in enumerate(chunks(items, RETRY_BATCH_SIZE), start=1):
                    retry_status.text(f"🔄 Retry batch {batch_idx} ({len(batch)} items, parallel {RETRY_MAX_WORKERS})")

                    with ThreadPoolExecutor(max_workers=RETRY_MAX_WORKERS) as ex:
                        futures = [ex.submit(retry_one, p, pr) for (p, pr) in batch]

                        done_in_batch = 0
                        for fut in as_completed(futures):
                            res = fut.result()
                            retry_results.append(res)

                            done_in_batch += 1
                            done_total = (batch_idx - 1) * RETRY_BATCH_SIZE + done_in_batch
                            retry_progress.progress(min(done_total / total, 1.0))

                            if res["status"].startswith("✅"):
                                retry_success += 1
                            else:
                                retry_error += 1

                    time.sleep(RETRY_SLEEP_BETWEEN_BATCHES)
                
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
                if len(final_result) > 50000:
                    st.warning("⚠️ Grote dataset: Excel export kan traag zijn of memory issues geven. Gebruik bij voorkeur CSV.")

                st.download_button(
                    label="📥 Download retry resultaten (Excel)",
                    data=convert_to_excel(retry_results_df),
                    file_name="priority_retry_resultaten.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="download_retry_results"
                )
    # ============================================
    # STAP 5: PUSH LEVERANCIERSPRIJSLIJST NAAR PRIORITY (PATCH)
    # ============================================
    st.divider()
    st.header("📦 Stap 5: Leveranciersprijslijst naar Priority")

    if 'final_result' not in st.session_state:
        st.warning("⚠️ Voer eerst een prijsvergelijking uit.")
        st.stop()

    final_result = st.session_state['final_result']
    status_col = 'Prijsstatus' if 'Prijsstatus' in final_result.columns else 'Status'

    # --------------------------------------------
    # HARD REQUIREMENT: priority_id moet bestaan
    # --------------------------------------------
    if 'priority_id' not in final_result.columns:
        st.error("❌ Kolom 'priority_id' ontbreekt in het resultaat. Voeg deze kolom toe aan je 'eigen' upload (hoofdfile).")
        st.stop()

    # ============================================
    # 5.1 PRIJSLIJST HEADER (SUPPRICELIST)
    # ============================================
    st.subheader("📋 Prijslijst gegevens (SUPPRICELIST)")

    col1, col2 = st.columns(2)

    with col1:
        suppl_name = st.text_input(
            "Prijslijstcode (SUPPLNAME):",
            value="",
            max_chars=8,
            key="suppl_name",
            help="Max 8 karakters - Unieke code voor deze prijslijst"
        )

        sup_name = st.text_input(
            "Leverancierscode (SUPNAME):",
            value="",
            max_chars=16,
            key="sup_name",
            help="Max 16 karakters - Code van de leverancier in Priority"
        )

    with col2:
        suppl_date = st.date_input(
            "Datum prijslijst (SUPPLDATE):",
            value=None,
            format="DD/MM/YYYY",
            key="suppl_date",
            help="Ingangsdatum van de prijslijst (dd/mm/jjjj)"
        )

        currency_code = st.text_input(
            "Valutacode (CODE):",
            value="EUR",
            max_chars=3,
            key="currency_code",
            help="Standaard: EUR"
        )

    with st.expander("➕ Extra prijslijst opties (optioneel)"):
        col1, col2 = st.columns(2)

        with col1:
            suppl_des = st.text_input(
                "Prijslijst omschrijving (SUPPLDES):",
                value="",
                max_chars=16,
                key="suppl_des",
                help="Max 16 karakters"
            )

            expiry_date = st.date_input(
                "Vervaldatum (EXPIRYDATE):",
                value=None,
                format="DD/MM/YYYY",
                key="expiry_date",
                help="Optioneel - Vervaldatum prijslijst"
            )

        with col2:
            mnf_name = st.text_input(
                "Fabrikantcode (MNFNAME):",
                value="",
                max_chars=10,
                key="mnf_name",
                help="Optioneel - Max 10 karakters"
            )

            multiply_price = st.number_input(
                "Prijsfactor (MULTIPLYPRICE):",
                value=1.0,
                min_value=0.0,
                step=0.01,
                key="multiply_price",
                help="Standaard: 1.0"
            )

    if not suppl_name or not sup_name or not suppl_date:
        st.warning("⚠️ Vul prijslijstcode, leverancierscode en datum in om verder te gaan.")
        st.stop()

    def format_date_for_priority(date_obj):
        """Converteer Python date naar Priority DateTimeOffset formaat"""
        if date_obj is None:
            return None
        return f"{date_obj.strftime('%Y-%m-%d')}T00:00:00+02:00"

    st.success(f"✅ Prijslijst: **{suppl_name}** voor leverancier **{sup_name}** per **{suppl_date.strftime('%d/%m/%Y')}**")

    # ============================================
    # 5.2 KOLOM MAPPING (SPARTPRICE)
    # ============================================
    st.subheader("🔗 Kolom Mapping (SPARTPRICE)")

    col1, col2 = st.columns(2)

    with col1:
        partname_candidates = [
            c for c in final_result.columns
            if any(x in c.lower() for x in ['article', 'artikel', 'partname', 'artikelnummer', 'article_code', 'supplier_code', 'code'])
        ]
        default_partname = partname_candidates[0] if partname_candidates else final_result.columns[0]

        spl_partname_col = st.selectbox(
            "Artikelnummer (→ PARTNAME):",
            options=final_result.columns.tolist(),
            index=final_result.columns.tolist().index(default_partname) if default_partname in final_result.columns else 0,
            key="spl_partname_col"
        )

        price_candidates = [c for c in final_result.columns if 'prijs' in c.lower() or 'price' in c.lower()]
        default_price = 'Nieuwe prijs' if 'Nieuwe prijs' in final_result.columns else (price_candidates[0] if price_candidates else final_result.columns[0])

        spl_price_col = st.selectbox(
            "Prijs (→ PRICE):",
            options=final_result.columns.tolist(),
            index=final_result.columns.tolist().index(default_price) if default_price in final_result.columns else 0,
            key="spl_price_col"
        )

    with col2:
        use_quant_col = st.checkbox("Aantal uit kolom halen", value=False, key="use_quant_col")

        if use_quant_col:
            quant_candidates = [c for c in final_result.columns if any(x in c.lower() for x in ['quant', 'aantal', 'qty', 'quantity', 'step'])]
            default_quant = quant_candidates[0] if quant_candidates else final_result.columns[0]

            spl_quant_col = st.selectbox(
                "Aantal (→ QUANT):",
                options=final_result.columns.tolist(),
                index=final_result.columns.tolist().index(default_quant) if default_quant in final_result.columns else 0,
                key="spl_quant_col"
            )
            default_quant_value = 1
        else:
            spl_quant_col = None
            default_quant_value = st.number_input(
                "Standaard aantal (QUANT):",
                min_value=1,
                value=1,
                key="default_quant_value"
            )

    # Extra preview kolommen
    available_extra_cols = [c for c in final_result.columns if c not in [spl_partname_col, spl_price_col, status_col, 'priority_id']]
    spl_extra_preview_cols = st.multiselect(
        "Extra kolommen in preview:",
        options=available_extra_cols,
        default=[c for c in available_extra_cols if any(x in c.lower() for x in ['name', 'naam', 'omschrijving', 'family', 'group'])][:3],
        key="spl_extra_preview_cols"
    )

    # ============================================
    # 5.3 FILTER SELECTIE
    # ============================================
    st.subheader("📊 Welke artikelen opnemen?")

    col1, col2, col3 = st.columns(3)
    with col1:
        spl_include_increases = st.checkbox("🔴 Prijsverhogingen", value=True, key="spl_include_increases")
    with col2:
        spl_include_decreases = st.checkbox("🟢 Prijsverlagingen", value=True, key="spl_include_decreases")
    with col3:
        spl_include_unchanged = st.checkbox("⚪ Ongewijzigd", value=False, key="spl_include_unchanged")

    spl_selected_statuses = []
    if spl_include_increases:
        spl_selected_statuses.append('🔴 Prijsverhoging')
    if spl_include_decreases:
        spl_selected_statuses.append('🟢 Prijsverlaging')
    if spl_include_unchanged:
        spl_selected_statuses.append('⚪ Ongewijzigd')

    if not spl_selected_statuses:
        st.warning("⚠️ Selecteer minimaal één categorie.")
        st.stop()

    # HARD FILTER: priority_id moet gevuld zijn
    spl_push_df = final_result[
        (final_result[status_col].isin(spl_selected_statuses)) &
        (final_result[spl_partname_col].notna()) &
        (final_result[spl_partname_col].astype(str).str.strip() != '') &
        (final_result[spl_partname_col].astype(str).str.lower() != 'nan') &
        (final_result['priority_id'].notna()) &
        (final_result['priority_id'].astype(str).str.strip() != '') &
        (final_result['priority_id'].astype(str).str.lower() != 'nan')
    ].copy()

    st.info(f"📋 {len(spl_push_df)} artikelen geselecteerd (met priority_id)")

    if len(spl_push_df) == 0:
        st.warning("⚠️ Geen artikelen gevonden met priority_id in de geselecteerde categorieën.")
        st.stop()

    # ============================================
    # 5.4 KORTINGEN CONFIGURATIE
    # ============================================
    st.subheader("💰 Kortingen (ZVAR_VDISC1, ZVAR_VDISC2, ZVAR_VDISC3)")

    discount_mode = st.radio(
        "Kortingen instellen:",
        options=[
            "❌ Geen kortingen (alleen prijs)",
            "📊 Vaste waarde voor hele prijslijst",
            "📁 Per familie/artikelgroep",
            "📋 Uit kolommen in bestand"
        ],
        key="discount_mode",
        horizontal=False
    )

    fixed_disc1 = 0.0
    fixed_disc2 = 0.0
    fixed_disc3 = 0.0
    group_discounts = {}
    discount_group_col = None
    disc1_col = None
    disc2_col = None
    disc3_col = None

    if discount_mode == "📊 Vaste waarde voor hele prijslijst":
        st.write("**Vaste kortingspercentages:**")
        c1, c2, c3 = st.columns(3)
        with c1:
            fixed_disc1 = st.number_input("Korting 1 (%):", 0.0, 100.0, 0.0, 0.5, key="fixed_disc1")
        with c2:
            fixed_disc2 = st.number_input("Korting 2 (%):", 0.0, 100.0, 0.0, 0.5, key="fixed_disc2")
        with c3:
            fixed_disc3 = st.number_input("Korting 3 (%):", 0.0, 100.0, 0.0, 0.5, key="fixed_disc3")

    elif discount_mode == "📁 Per familie/artikelgroep":
        group_col_candidates = [c for c in final_result.columns if any(x in c.lower() for x in ['group', 'family', 'categor', 'groep', 'familie', 'lijn', 'line'])]
        discount_group_col = st.selectbox(
            "Groepeer op kolom:",
            options=final_result.columns.tolist(),
            index=final_result.columns.tolist().index(group_col_candidates[0]) if group_col_candidates else 0,
            key="discount_group_col"
        )

        unique_groups = spl_push_df[discount_group_col].dropna().unique().tolist()
        unique_groups = sorted([str(g) for g in unique_groups if str(g).strip() != ''])

        if 0 < len(unique_groups) <= 100:
            st.caption("💡 Tip: Je kunt waardes kopiëren/plakken in de tabel (Ctrl+C / Ctrl+V)")

            group_discount_df = pd.DataFrame({
                'Groep': unique_groups,
                'Korting 1 (%)': [0.0] * len(unique_groups),
                'Korting 2 (%)': [0.0] * len(unique_groups),
                'Korting 3 (%)': [0.0] * len(unique_groups)
            })

            edited_group_discounts = st.data_editor(
                group_discount_df,
                hide_index=True,
                use_container_width=True,
                num_rows="fixed",
                key="group_discount_editor"
            )

            for _, row in edited_group_discounts.iterrows():
                group_discounts[str(row['Groep'])] = (
                    float(row['Korting 1 (%)']),
                    float(row['Korting 2 (%)']),
                    float(row['Korting 3 (%)'])
                )
        else:
            st.warning("⚠️ Geen/te veel groepen gevonden. Kies andere kortingmodus.")
            discount_mode = "❌ Geen kortingen (alleen prijs)"

    elif discount_mode == "📋 Uit kolommen in bestand":
        options = ['(geen)'] + final_result.columns.tolist()
        c1, c2, c3 = st.columns(3)
        with c1:
            disc1_col = st.selectbox("Korting 1 kolom:", options=options, index=0, key="disc1_col")
            if disc1_col == '(geen)': disc1_col = None
        with c2:
            disc2_col = st.selectbox("Korting 2 kolom:", options=options, index=0, key="disc2_col")
            if disc2_col == '(geen)': disc2_col = None
        with c3:
            disc3_col = st.selectbox("Korting 3 kolom:", options=options, index=0, key="disc3_col")
            if disc3_col == '(geen)': disc3_col = None

    def parse_price(value):
        if pd.isna(value) or value is None:
            return None
        try:
            return float(str(value).replace(',', '.').replace('€', '').replace(' ', '').strip())
        except:
            return None

    def parse_quantity(value, default_val=1):
        if pd.isna(value) or value is None:
            return default_val
        try:
            return int(float(str(value).replace(',', '.').strip()))
        except:
            return default_val

    def parse_pct(v):
        if pd.isna(v) or str(v).strip() == '':
            return 0.0
        try:
            return float(str(v).replace(',', '.').replace('%', '').strip())
        except:
            return 0.0

    spl_push_df['_price'] = spl_push_df[spl_price_col].apply(parse_price)
    spl_push_df = spl_push_df[spl_push_df['_price'].notna()].copy()

    if spl_quant_col:
        spl_push_df['_quant'] = spl_push_df[spl_quant_col].apply(lambda v: parse_quantity(v, default_quant_value))
    else:
        spl_push_df['_quant'] = int(default_quant_value)

    # kortingen
    if discount_mode == "❌ Geen kortingen (alleen prijs)":
        spl_push_df['_disc1'] = None
        spl_push_df['_disc2'] = None
        spl_push_df['_disc3'] = None
    elif discount_mode == "📊 Vaste waarde voor hele prijslijst":
        spl_push_df['_disc1'] = fixed_disc1
        spl_push_df['_disc2'] = fixed_disc2
        spl_push_df['_disc3'] = fixed_disc3
    elif discount_mode == "📁 Per familie/artikelgroep":
        def grp(row):
            key = str(row.get(discount_group_col, ""))
            d = group_discounts.get(key, (0.0, 0.0, 0.0))
            return d
        vals = spl_push_df.apply(grp, axis=1)
        spl_push_df['_disc1'] = [v[0] for v in vals]
        spl_push_df['_disc2'] = [v[1] for v in vals]
        spl_push_df['_disc3'] = [v[2] for v in vals]
    else:
        spl_push_df['_disc1'] = spl_push_df[disc1_col].apply(parse_pct) if disc1_col else None
        spl_push_df['_disc2'] = spl_push_df[disc2_col].apply(parse_pct) if disc2_col else None
        spl_push_df['_disc3'] = spl_push_df[disc3_col].apply(parse_pct) if disc3_col else None

    # ============================================
    # 5.6 PREVIEW
    # ============================================
    st.subheader("👁️ Preview")

    preview_cols = [spl_partname_col, 'priority_id'] + spl_extra_preview_cols + ['_quant', '_price']

    if discount_mode != "❌ Geen kortingen (alleen prijs)":
        preview_cols += ['_disc1', '_disc2', '_disc3']

    preview_cols += [status_col]

    preview_cols = [c for c in preview_cols if c in spl_push_df.columns]
    preview_cols = unique_list(preview_cols)

    preview_df = spl_push_df[preview_cols].copy()
    preview_df = preview_df.rename(columns={
        '_quant': 'Aantal',
        '_price': 'Prijs',
        '_disc1': 'Korting 1 (%)',
        '_disc2': 'Korting 2 (%)',
        '_disc3': 'Korting 3 (%)'
    })

    st.dataframe(
        preview_df.head(50),
        use_container_width=True,
        hide_index=True
    )

    if len(spl_push_df) > 50:
        st.caption(f"... en {len(spl_push_df) - 50} meer artikelen")
    
    # ============================================
    # 5.7 PUSH NAAR PRIORITY (PATCH) - CHUNKS VAN 500
    # ============================================
    st.divider()
    st.subheader("🚀 5.7 Patch leveranciersprijslijst naar Priority (SUPPRICELIST)")

    PRIORITY_BASE = "https://p.priority-connect.online/odata/Priority/tabCA637.ini/vareydb/"
    PRIORITY_AUTH = "Basic Q0E5RTFDNTgxNEJENDNEMEI3RDlBNTI1RDFCOThGQ0Y6UEFU"

    # Test mode (standaard UIT)
    spl_dry_run = st.checkbox("🧪 Test mode", value=False, key="spl_dry_run")

    # Kortingen meesturen?
    include_discounts = st.checkbox(
        "Kortingen meesturen (ZVAR_VDISC1/2/3)",
        value=True,
        help="Zet uit om alleen PARTNAME, QUANT en PRICE te patchen.",
        key="spl_include_discounts"
    )

    # Chunk settings
    CHUNK_SIZE = st.number_input("Chunk grootte", min_value=50, max_value=1000, value=500, step=50, key="spl_chunk_size")
    TIMEOUT_SECONDS = st.number_input("Timeout per chunk (sec)", min_value=60, max_value=600, value=300, step=30, key="spl_timeout")
    SLEEP_BETWEEN = st.number_input("Pauze tussen chunks (sec)", min_value=0.0, max_value=5.0, value=0.3, step=0.1, key="spl_sleep_between")

    st.write("**Prijslijst key:**")
    st.json({
        "SUPPLNAME": suppl_name,
        "SUPNAME": sup_name,
        "SUPPLDATE": suppl_date.strftime('%d/%m/%Y'),
        "CODE": currency_code
    })

    def build_header_payload():
        # Alleen de velden die jij wil patchen in de header
        return {
            "SUPPLNAME": suppl_name,
            "SUPNAME": sup_name,
            "SUPPLDATE": format_date_for_priority(suppl_date),
            "CODE": currency_code
        }

    def build_subform_items(df: pd.DataFrame):
        items_local = []
        for _, row in df.iterrows():
            item = {
                "PARTNAME": str(row[spl_partname_col]).strip(),
                "QUANT": int(row["_quant"]),
                "PRICE": round(float(row["_price"]), 2)
            }

            # Kortingen optioneel
            if include_discounts and discount_mode != "❌ Geen kortingen (alleen prijs)":
                d1 = row.get("_disc1", None)
                d2 = row.get("_disc2", None)
                d3 = row.get("_disc3", None)

                if d1 is not None:
                    item["ZVAR_VDISC1"] = round(float(d1), 2)
                if d2 is not None:
                    item["ZVAR_VDISC2"] = round(float(d2), 2)
                if d3 is not None:
                    item["ZVAR_VDISC3"] = round(float(d3), 2)

            items_local.append(item)
        return items_local

    def chunks(lst, n):
        for i in range(0, len(lst), n):
            yield lst[i:i + n]

    # Bouw subform items (één keer)
    subform_items = build_subform_items(spl_push_df)
    chunk_count = (len(subform_items) + int(CHUNK_SIZE) - 1) // int(CHUNK_SIZE)

    st.info(f"📦 Te patchen items: {len(subform_items)} (chunks: {chunk_count} × max {int(CHUNK_SIZE)})")

    # Debug preview payload
    with st.expander("🔧 Debug: payload preview (chunk 1, eerste 5 items)"):
        preview_payload = build_header_payload()
        preview_payload["SPARTPRICE_SUBFORM"] = subform_items[:5]
        st.json(preview_payload)

    col1, col2 = st.columns([3, 1])
    with col1:
        spl_push_button = st.button(
            f"✏️ Patch prijslijst ({chunk_count} chunks)",
            type="primary",
            use_container_width=True,
            key="spl_push_to_priority"
        )
    with col2:
        retry_same = st.button(
            "🔄 Retry laatste run",
            use_container_width=True,
            key="spl_retry_last"
        )

    # Kleine helper om te kunnen retryen zonder opnieuw te bouwen
    def run_patch_chunks():
        import requests
        import time as _time

        headers = {"Authorization": PRIORITY_AUTH, "Content-Type": "application/json"}
        formatted_date = format_date_for_priority(suppl_date)
        url = f"{PRIORITY_BASE}SUPPRICELIST(SUPPLNAME='{suppl_name}',SUPPLDATE={formatted_date})"

        all_chunk_results = []
        failed = False

        progress = st.progress(0.0)
        status = st.empty()

        if spl_dry_run:
            # Simuleer
            for idx, chunk_items in enumerate(chunks(subform_items, int(CHUNK_SIZE)), start=1):
                all_chunk_results.append({
                    "chunk": idx,
                    "items": len(chunk_items),
                    "http_status": "TEST",
                    "ok": True,
                    "response_preview": ""
                })
                progress.progress(idx / max(chunk_count, 1))
                status.text(f"🧪 Test mode - chunk {idx}/{chunk_count} ({len(chunk_items)} items)")
                _time.sleep(0.01)

            progress.empty()
            status.empty()

            st.success(f"🧪 Test mode: zou {len(subform_items)} items patchen in {chunk_count} chunks.")
            return all_chunk_results, failed, url, headers

        with st.spinner("Bezig met patchen van prijslijst in chunks..."):
            for idx, sub_items_chunk in enumerate(chunks(subform_items, int(CHUNK_SIZE)), start=1):

                # Chunk payload: header enkel in chunk 1
                if idx == 1:
                    chunk_payload = build_header_payload()
                    chunk_payload["SPARTPRICE_SUBFORM"] = sub_items_chunk
                else:
                    chunk_payload = {"SPARTPRICE_SUBFORM": sub_items_chunk}

                status.text(f"⏳ Chunk {idx}/{chunk_count} - items {len(sub_items_chunk)}")

                try:
                    resp = requests.patch(
                        url,
                        json=chunk_payload,
                        headers=headers,
                        timeout=int(TIMEOUT_SECONDS)
                    )
                except requests.exceptions.Timeout:
                    failed = True
                    all_chunk_results.append({
                        "chunk": idx,
                        "items": len(sub_items_chunk),
                        "http_status": "TIMEOUT",
                        "ok": False,
                        "response_preview": "Timeout"
                    })
                    st.error(f"❌ Chunk {idx} timeout")
                    break
                except requests.exceptions.RequestException as e:
                    failed = True
                    all_chunk_results.append({
                        "chunk": idx,
                        "items": len(sub_items_chunk),
                        "http_status": "REQUEST_ERROR",
                        "ok": False,
                        "response_preview": str(e)[:300]
                    })
                    st.error(f"❌ Chunk {idx} request error")
                    st.code(str(e))
                    break

                ok = resp.status_code in (200, 204)
                all_chunk_results.append({
                    "chunk": idx,
                    "items": len(sub_items_chunk),
                    "http_status": resp.status_code,
                    "ok": ok,
                    "response_preview": (resp.text[:300] if resp.text else "")
                })

                if not ok:
                    failed = True
                    st.error(f"❌ Chunk {idx} mislukt: HTTP {resp.status_code}")
                    if resp.text:
                        st.code(resp.text[:1500])
                    break

                progress.progress(idx / max(chunk_count, 1))
                _time.sleep(float(SLEEP_BETWEEN))

        progress.empty()
        status.empty()

        return all_chunk_results, failed, url, headers

    # Execute / Retry
    if spl_push_button:
        all_chunk_results, failed, last_url, last_headers = run_patch_chunks()

        # Bewaar voor retry
        st.session_state["spl_last_chunk_results"] = all_chunk_results
        st.session_state["spl_last_failed"] = failed

        st.write("📦 Chunk resultaten:")
        st.dataframe(pd.DataFrame(all_chunk_results), use_container_width=True, hide_index=True)

        if not failed:
            st.success(f"🎉 Prijslijst **{suppl_name}** succesvol gepatcht in {len(all_chunk_results)} chunks.")
        else:
            st.warning("⚠️ Patch stopte door een fout. Zie chunk resultaten hierboven.")

        # Downloads
        st.subheader("📥 Download")

        d1, d2 = st.columns(2)
        with d1:
            import json
            payload_for_download = build_header_payload()
            payload_for_download["SPARTPRICE_SUBFORM"] = subform_items  # volledige lijst (ter referentie)
            st.download_button(
                "📥 Download payload (JSON)",
                data=json.dumps(payload_for_download, indent=2, ensure_ascii=False),
                file_name=f"priority_suppricelist_payload_{suppl_name}_{suppl_date.strftime('%Y%m%d')}.json",
                mime="application/json",
                key="download_spl_payload_json_full"
            )

        with d2:
            export_df = spl_push_df[[spl_partname_col, "_quant", "_price"]].copy()
            export_df.columns = ["Artikelnummer", "Aantal", "Prijs"]
            if include_discounts and discount_mode != "❌ Geen kortingen (alleen prijs)":
                export_df["Korting 1 (%)"] = spl_push_df.get("_disc1", None)
                export_df["Korting 2 (%)"] = spl_push_df.get("_disc2", None)
                export_df["Korting 3 (%)"] = spl_push_df.get("_disc3", None)

            st.download_button(
                "📥 Download artikellijst (Excel)",
                data=convert_to_excel(export_df),
                file_name=f"priority_suppricelist_items_{suppl_name}_{suppl_date.strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_spl_items_excel"
            )

    if retry_same:
        last = st.session_state.get("spl_last_chunk_results")
        if not last:
            st.info("Geen vorige run gevonden om te retryen.")
        else:
            st.info("Retrying met huidige instellingen (chunks/timeout)...")
            all_chunk_results, failed, _, _ = run_patch_chunks()

            st.session_state["spl_last_chunk_results"] = all_chunk_results
            st.session_state["spl_last_failed"] = failed

            st.write("📦 Chunk resultaten (retry):")
            st.dataframe(pd.DataFrame(all_chunk_results), use_container_width=True, hide_index=True)

            if not failed:
                st.success("🎉 Retry succesvol!")
            else:
                st.warning("⚠️ Retry stopte door een fout. Zie chunk resultaten hierboven.")
    
    # ============================================
    # 5.8 RETRY BIJ FOUT
    # ============================================
    if 'spl_push_result' in st.session_state:
        result = st.session_state['spl_push_result']
        
        if result['status'] in ['error', 'timeout', 'connection_error']:
            st.divider()
            st.subheader("🔄 Opnieuw proberen")
            
            st.warning(f"De vorige poging is mislukt. Je kunt het opnieuw proberen.")
            
            if result['status'] == 'timeout':
                st.info("💡 Tip: Bij een timeout kun je proberen om minder artikelen tegelijk te versturen.")
                
                # Optie om in batches te versturen
                batch_size = st.number_input(
                    "Batch grootte (artikelen per request):",
                    min_value=10,
                    max_value=500,
                    value=100,
                    step=10,
                    key="spl_batch_size"
                )
                
                if st.button("🔄 Retry in batches", key="spl_retry_batches"):
                    st.info("⚠️ Batch modus is nog niet geïmplementeerd. Neem contact op met support.")
            
            else:
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    if st.button("🔄 Opnieuw proberen", type="secondary", use_container_width=True, key="spl_retry"):
                        # Reset result en herlaad pagina
                        del st.session_state['spl_push_result']
                        st.rerun()
                
                with col2:
                    # Optie om test mode te gebruiken
                    st.checkbox("🧪 Als test", value=True, key="spl_retry_test")
    # ============================================
    # STAP 6: EXPORT VOOR WEBSHOP (XANO IMPORT)
    # ============================================
    st.divider()
    st.header("📤 Stap 6: Export voor webshop import (Xano)")

    if 'final_result' not in st.session_state:
        st.warning("⚠️ Voer eerst een prijsvergelijking uit.")
        st.stop()

    final_result = st.session_state['final_result']
    status_col = 'Prijsstatus' if 'Prijsstatus' in final_result.columns else 'Status'

    # ----------------------------
    # 6.1 Prijslijst info
    # ----------------------------
    st.subheader("📋 Prijslijst info")

    c1, c2, c3 = st.columns(3)
    with c1:
        xano_pricelist_name = st.text_input(
            "pricelist_name:",
            value="",
            key="xano_export_pricelist_name"
        )
    with c2:
        xano_pricelist_date = st.date_input(
            "pricelist_date (dd/mm/jjjj):",
            value=None,
            format="DD/MM/YYYY",
            key="xano_export_pricelist_date"
        )
    with c3:
        xano_pricelist_quantity = st.number_input(
            "pricelist_quantity (standaard):",
            min_value=1,
            value=1,
            key="xano_export_pricelist_quantity"
        )

    if not xano_pricelist_name or not xano_pricelist_date:
        st.warning("⚠️ Vul pricelist_name en datum in.")
        st.stop()

    # Jij gaf aan dat Xano import vaak "Jun 1, 2025" verwacht in CSV-upload
    def format_date_for_xano_import(date_obj):
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        return f"{months[date_obj.month - 1]} {date_obj.day}, {date_obj.year}"

    date_format_choice = st.radio(
        "Datumformaat in export:",
        options=["Jun 1, 2025 (Xano upload)", "2025-06-01 (ISO)"],
        horizontal=True,
        key="xano_export_date_format"
    )

    if date_format_choice.startswith("Jun"):
        export_date_str = format_date_for_xano_import(xano_pricelist_date)
    else:
        export_date_str = xano_pricelist_date.strftime("%Y-%m-%d")

    st.info(f"📅 Export datum wordt: **{export_date_str}**")

    # ----------------------------
    # 6.2 Mapping
    # ----------------------------
    st.subheader("🔗 Kolom mapping")

    c1, c2 = st.columns(2)

    with c1:
        id_candidates = [c for c in final_result.columns if c.lower() == 'id' or 'xano' in c.lower() or 'webshop_id' in c.lower()]
        default_id = 'id' if 'id' in final_result.columns else (id_candidates[0] if id_candidates else final_result.columns[0])

        xano_id_col = st.selectbox(
            "Kolom met Xano id (verplicht):",
            options=final_result.columns.tolist(),
            index=final_result.columns.tolist().index(default_id) if default_id in final_result.columns else 0,
            key="xano_export_id_col"
        )

    with c2:
        price_candidates = [c for c in final_result.columns if 'prijs' in c.lower() or 'price' in c.lower()]
        default_price = 'Nieuwe prijs' if 'Nieuwe prijs' in final_result.columns else (price_candidates[0] if price_candidates else final_result.columns[0])

        xano_price_col = st.selectbox(
            "Kolom met nieuwe prijs:",
            options=final_result.columns.tolist(),
            index=final_result.columns.tolist().index(default_price) if default_price in final_result.columns else 0,
            key="xano_export_price_col"
        )

    # ----------------------------
    # 6.3 Filter selectie
    # ----------------------------
    st.subheader("📊 Welke artikelen opnemen?")

    c1, c2, c3 = st.columns(3)
    with c1:
        inc_up = st.checkbox("🔴 Prijsverhogingen", value=True, key="xano_export_inc_up")
    with c2:
        inc_down = st.checkbox("🟢 Prijsverlagingen", value=True, key="xano_export_inc_down")
    with c3:
        inc_same = st.checkbox("⚪ Ongewijzigd", value=False, key="xano_export_inc_same")

    selected = []
    if inc_up: selected.append("🔴 Prijsverhoging")
    if inc_down: selected.append("🟢 Prijsverlaging")
    if inc_same: selected.append("⚪ Ongewijzigd")

    if not selected:
        st.warning("⚠️ Selecteer minimaal één status.")
        st.stop()

    export_df = final_result[
        (final_result[status_col].isin(selected)) &
        (final_result[xano_id_col].notna()) &
        (final_result[xano_id_col].astype(str).str.strip() != '') &
        (final_result[xano_id_col].astype(str).str.lower() != 'nan')
    ].copy()

    st.info(f"📦 {len(export_df)} artikelen geselecteerd voor export")

    if len(export_df) == 0:
        st.warning("⚠️ Geen rijen om te exporteren (check id kolom + filters).")
        st.stop()

    # ----------------------------
    # 6.4 Kortingen (zelfde opties)
    # ----------------------------
    st.subheader("💰 Kortingen (optioneel)")

    disc_mode = st.radio(
        "Kortingen invullen:",
        options=[
            "❌ Geen kortingen (leeg laten)",
            "📊 Vaste waarde voor alle artikelen",
            "📁 Per familie/artikelgroep",
            "📋 Uit kolommen in bestand"
        ],
        key="xano_export_disc_mode"
    )

    disc1_col = disc2_col = disc3_col = None
    fixed1 = fixed2 = fixed3 = 0.0
    group_map = {}
    group_col = None

    if disc_mode == "📊 Vaste waarde voor alle artikelen":
        d1, d2, d3 = st.columns(3)
        with d1:
            fixed1 = st.number_input("disc1 (%)", 0.0, 100.0, 0.0, 0.5, key="xano_export_fixed1")
        with d2:
            fixed2 = st.number_input("disc2 (%)", 0.0, 100.0, 0.0, 0.5, key="xano_export_fixed2")
        with d3:
            fixed3 = st.number_input("disc3 (%)", 0.0, 100.0, 0.0, 0.5, key="xano_export_fixed3")

    elif disc_mode == "📁 Per familie/artikelgroep":
        group_candidates = [c for c in final_result.columns if any(x in c.lower() for x in ['group', 'family', 'categor', 'groep', 'familie', 'lijn', 'line'])]
        group_col = st.selectbox(
            "Groepeer op kolom:",
            options=final_result.columns.tolist(),
            index=final_result.columns.tolist().index(group_candidates[0]) if group_candidates else 0,
            key="xano_export_group_col"
        )

        groups = sorted([str(g) for g in export_df[group_col].dropna().unique() if str(g).strip() != ''])
        if len(groups) == 0:
            st.warning("⚠️ Geen groepen gevonden.")
        else:
            st.caption("Kopieer/plak waardes in de tabel indien gewenst.")
            group_discount_df = pd.DataFrame({
                "Groep": groups,
                "disc1": [0.0]*len(groups),
                "disc2": [0.0]*len(groups),
                "disc3": [0.0]*len(groups),
            })
            edited = st.data_editor(
                group_discount_df,
                hide_index=True,
                use_container_width=True,
                key="xano_export_group_editor"
            )
            for _, r in edited.iterrows():
                group_map[str(r["Groep"])] = (float(r["disc1"]), float(r["disc2"]), float(r["disc3"]))

    elif disc_mode == "📋 Uit kolommen in bestand":
        options = ['(geen)'] + final_result.columns.tolist()
        d1, d2, d3 = st.columns(3)
        with d1:
            disc1_col = st.selectbox("disc1 kolom", options=options, index=0, key="xano_export_disc1_col")
            if disc1_col == '(geen)': disc1_col = None
        with d2:
            disc2_col = st.selectbox("disc2 kolom", options=options, index=0, key="xano_export_disc2_col")
            if disc2_col == '(geen)': disc2_col = None
        with d3:
            disc3_col = st.selectbox("disc3 kolom", options=options, index=0, key="xano_export_disc3_col")
            if disc3_col == '(geen)': disc3_col = None

    def parse_pct(v):
        if pd.isna(v) or str(v).strip() == '':
            return None
        try:
            return float(str(v).replace(',', '.').replace('%', '').strip())
        except:
            return None

    def parse_price_dot(v):
        if pd.isna(v) or str(v).strip() == '':
            return None
        try:
            return float(str(v).replace('€', '').replace(' ', '').replace(',', '.').strip())
        except:
            return None

    export_df["_xano_price"] = export_df[xano_price_col].apply(parse_price_dot)
    export_df = export_df[export_df["_xano_price"].notna()].copy()

    # discounts
    if disc_mode == "❌ Geen kortingen (leeg laten)":
        export_df["_disc1"] = None
        export_df["_disc2"] = None
        export_df["_disc3"] = None
    elif disc_mode == "📊 Vaste waarde voor alle artikelen":
        export_df["_disc1"] = fixed1
        export_df["_disc2"] = fixed2
        export_df["_disc3"] = fixed3
    elif disc_mode == "📁 Per familie/artikelgroep":
        def grp(row):
            key = str(row.get(group_col, ""))
            return group_map.get(key, (None, None, None))
        vals = export_df.apply(grp, axis=1)
        export_df["_disc1"] = [v[0] for v in vals]
        export_df["_disc2"] = [v[1] for v in vals]
        export_df["_disc3"] = [v[2] for v in vals]
    else:  # kolommen
        export_df["_disc1"] = export_df[disc1_col].apply(parse_pct) if disc1_col else None
        export_df["_disc2"] = export_df[disc2_col].apply(parse_pct) if disc2_col else None
        export_df["_disc3"] = export_df[disc3_col].apply(parse_pct) if disc3_col else None

    # ----------------------------
    # 6.5 Bouw exportformaat
    # ----------------------------
    out = pd.DataFrame()
    out["id"] = export_df[xano_id_col].astype(str).str.replace(".0", "", regex=False)
    out["price"] = pd.to_numeric(export_df["_xano_price"], errors="coerce").round(2)
    out["pricelist_name"] = xano_pricelist_name
    out["pricelist_date"] = export_date_str
    out["pricelist_quantity"] = int(xano_pricelist_quantity)
    out["pricelist_price"] = pd.to_numeric(export_df["_xano_price"], errors="coerce").round(2)

    # Optioneel: discs alleen toevoegen als niet alles leeg is
    if not (export_df["_disc1"].isna().all() and export_df["_disc2"].isna().all() and export_df["_disc3"].isna().all()):
        out["pricelist_disc1"] = export_df["_disc1"]
        out["pricelist_disc2"] = export_df["_disc2"]
        out["pricelist_disc3"] = export_df["_disc3"]

    st.subheader("👀 Preview export")
    st.dataframe(out.head(50), use_container_width=True, hide_index=True)

    st.subheader("📥 Download")
    c1, c2 = st.columns(2)

    with c1:
        st.download_button(
            "📥 Download Excel (Xano import)",
            data=convert_to_excel(out),
            file_name=f"xano_import_{xano_pricelist_name}_{xano_pricelist_date.strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="download_xano_import_excel"
        )

    with c2:
        # CSV met punt-decimaal (we bouwen even expliciet)
        csv_bytes = out.to_csv(index=False, sep=",", decimal=".", encoding="utf-8").encode("utf-8")
        st.download_button(
            "📥 Download CSV (Xano import)",
            data=csv_bytes,
            file_name=f"xano_import_{xano_pricelist_name}_{xano_pricelist_date.strftime('%Y%m%d')}.csv",
            mime="text/csv",
            key="download_xano_import_csv"
        )
        # ============================================
