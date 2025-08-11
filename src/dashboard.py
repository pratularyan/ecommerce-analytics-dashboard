"""
src/dashboard.py
Ecommerce Analytics Dashboard
- Filters: date range, product category
- Dynamic KPIs that respond to filters
- Line chart, orders bar chart, top categories chart
- Automated short 'insights' text
"""

from pathlib import Path
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import timedelta

st.set_page_config(page_title="Ecommerce Analytics Dashboard", layout="wide")

@st.cache_data
def load_data():
    # Robust path: project_root/data/processed/ecommerce_clean.csv
    base_dir = Path(__file__).resolve().parent.parent
    data_file = base_dir / "data" / "processed" / "ecommerce_clean.csv"
    df = pd.read_csv(data_file, parse_dates=['order_purchase_timestamp'], low_memory=False)

    # Ensure expected columns exist (defensive coding)
    if 'order_total' not in df.columns:
        # If you stored per-item price, try to compute order_total at least per row
        if 'price' in df.columns:
            df['order_total'] = df['price'].fillna(0) + df.get('freight_value', 0).fillna(0)
        else:
            df['order_total'] = 0.0

    # create helpful columns
    df['order_month'] = df['order_purchase_timestamp'].dt.to_period('M').dt.to_timestamp()
    df['order_date'] = df['order_purchase_timestamp'].dt.date
    df['product_category_name'] = df.get('product_category_name', pd.Series(['unknown'] * len(df)))
    return df

def format_currency(x):
    # Simple BRL formatting - adjust if needed
    try:
        return f"BRL {x:,.2f}"
    except Exception:
        return str(x)

def compute_kpis(df_filtered):
    # total revenue, number of orders, avg order value (AOV), unique customers
    total_rev = df_filtered['order_total'].sum()
    orders = df_filtered['order_id'].nunique()
    aov = total_rev / orders if orders > 0 else 0
    customers = df_filtered['customer_id'].nunique() if 'customer_id' in df_filtered.columns else np.nan
    return dict(total_revenue=total_rev, orders=orders, aov=aov, customers=customers)

def generate_insights(df, df_filtered):
    # compare last full month vs previous month
    # pick two last months available in filtered df (if possible)
    months = sorted(df_filtered['order_month'].unique())
    insight_lines = []

    if len(months) >= 2:
        last = months[-1]
        prev = months[-2]
        rev_by_month = df_filtered.groupby('order_month')['order_total'].sum()
        last_rev = float(rev_by_month.get(last, 0))
        prev_rev = float(rev_by_month.get(prev, 0))
        if prev_rev == 0:
            pct = None
        else:
            pct = (last_rev - prev_rev) / prev_rev * 100

        if pct is None:
            insight_lines.append(f"Revenue in {last.strftime('%b %Y')}: {format_currency(last_rev)} (no previous month data to compare).")
        else:
            sign = "increased" if pct > 0 else "decreased"
            insight_lines.append(f"Revenue {sign} {abs(pct):.1f}% in {last.strftime('%b %Y')} vs {prev.strftime('%b %Y')} — {format_currency(last_rev)} vs {format_currency(prev_rev)}.")

    # top category in filtered set
    cat_rev = df_filtered.groupby('product_category_name')['order_total'].sum().sort_values(ascending=False)
    if not cat_rev.empty:
        top_cat = cat_rev.index[0]
        top_val = cat_rev.iloc[0]
        insight_lines.append(f"Top category (by revenue): {top_cat} — {format_currency(top_val)}.")

    # orders trend: last 30 days vs previous 30 days
    latest_date = df_filtered['order_purchase_timestamp'].max()
    if pd.notnull(latest_date):
        last_30_start = latest_date - pd.Timedelta(days=29)
        prev_30_start = last_30_start - pd.Timedelta(days=30)
        last_30 = df_filtered[df_filtered['order_purchase_timestamp'] >= last_30_start]
        prev_30 = df_filtered[(df_filtered['order_purchase_timestamp'] >= prev_30_start) & (df_filtered['order_purchase_timestamp'] < last_30_start)]
        last_30_orders = last_30['order_id'].nunique()
        prev_30_orders = prev_30['order_id'].nunique()
        if prev_30_orders > 0:
            pct_orders = (last_30_orders - prev_30_orders) / prev_30_orders * 100
            insight_lines.append(f"Orders in the most recent 30 days {'increased' if pct_orders>0 else 'decreased'} {abs(pct_orders):.1f}% compared to prior 30 days.")
        else:
            insight_lines.append(f"Orders in last 30 days: {last_30_orders} (no prior 30-day comparison available).")

    return insight_lines

def main():
    df = load_data()

    # Sidebar - Filters
    st.sidebar.header("Filters")
    # Date range
    min_date = df['order_purchase_timestamp'].min().date()
    max_date = df['order_purchase_timestamp'].max().date()
    start_date, end_date = st.sidebar.date_input("Purchase date range", value=(min_date, max_date), min_value=min_date, max_value=max_date)

    # Category selector (multi-select)
    categories = df['product_category_name'].fillna("unknown").unique().tolist()
    categories_sorted = sorted(categories)
    selected_cats = st.sidebar.multiselect("Product categories", options=categories_sorted, default=categories_sorted[:6])

    # Apply filters
    if isinstance(start_date, list) or isinstance(start_date, tuple):
        start_date, end_date = start_date
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)  # end of day inclusive

    mask = (df['order_purchase_timestamp'] >= start_dt) & (df['order_purchase_timestamp'] <= end_dt)
    if selected_cats:
        mask = mask & df['product_category_name'].isin(selected_cats)
    df_filtered = df[mask].copy()

    # Layout - top KPI cards
    kpis = compute_kpis(df_filtered)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Revenue", format_currency(kpis['total_revenue']))
    col2.metric("Orders", f"{kpis['orders']:,}")
    col3.metric("Avg Order Value (AOV)", format_currency(kpis['aov']))
    col4.metric("Unique Customers", f"{int(kpis['customers']):,}" if not np.isnan(kpis['customers']) else "N/A")

    st.markdown("---")

    # Charts area: two columns for charts
    c1, c2 = st.columns((2,1))

    # Revenue over time (line)
    if df_filtered.empty:
        c1.write("No data for selected filters.")
    else:
        rev_time = df_filtered.groupby('order_month')['order_total'].sum().reset_index()
        fig_rev = px.line(rev_time, x='order_month', y='order_total',
                          labels={'order_month':'Month','order_total':'Revenue'},
                          title='Monthly Revenue')
        fig_rev.update_layout(yaxis_title="Revenue (BRL)")
        c1.plotly_chart(fig_rev, use_container_width=True)

        # Orders per month (bar)
        orders_time = df_filtered.groupby('order_month')['order_id'].nunique().reset_index()
        fig_ord = px.bar(orders_time, x='order_month', y='order_id', labels={'order_month':'Month','order_id':'Orders'},
                         title='Orders per Month')
        c1.plotly_chart(fig_ord, use_container_width=True)

    # Top product categories by revenue
    cat_rev = df_filtered.groupby('product_category_name')['order_total'].sum().reset_index().sort_values('order_total', ascending=False).head(10)
    fig_cat = px.bar(cat_rev, x='order_total', y='product_category_name', orientation='h',
                     labels={'order_total':'Revenue','product_category_name':'Category'},
                     title='Top 10 Categories by Revenue')
    fig_cat.update_layout(yaxis={'categoryorder':'total ascending'})
    c2.plotly_chart(fig_cat, use_container_width=True)

    st.markdown("---")
    # Insights
    st.subheader("Automated Insights")
    insights = generate_insights(df, df_filtered)
    for line in insights:
        st.write("•", line)

    # Download filtered data
    def convert_df_to_csv_bytes(df_to_convert):
        return df_to_convert.to_csv(index=False).encode('utf-8')

    if not df_filtered.empty:
        csv_bytes = convert_df_to_csv_bytes(df_filtered)
        st.download_button("Download filtered CSV", data=csv_bytes, file_name="filtered_ecommerce.csv", mime="text/csv")

    # Footer / notes
    st.caption("Tip: use the sidebar filters to explore different segments. This dashboard is suitable for demoing core analytics skills.")
    st.markdown("### Last updated")
    st.write(f"Data range: {min_date} — {max_date}")

if __name__ == "__main__":
    main()
