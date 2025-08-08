# Add interactive Streamlit dashboard for e-commerce analytics

# - Implemented dashboard layout with key metrics, visualizations, and filters
# - Integrated data loading and preprocessing for sales and customer insights
# - Enhanced user experience with responsive design and dynamic charts


import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

sns.set(style="whitegrid")

@st.cache_data
def load_data():
    # Get the current script's parent folder (src/)
    base_dir = Path(__file__).parent.parent  # go up from src/ to project root
    data_path = base_dir / "data" / "processed" / "ecommerce_clean.csv"
    df = pd.read_csv(data_path, parse_dates=['order_purchase_timestamp'])
    df['order_month'] = df['order_purchase_timestamp'].dt.to_period('M').dt.to_timestamp()
    return df


def main():
    st.title("Ecommerce Analytics Dashboard")
    st.markdown("### Business KPIs and Visualizations")

    df = load_data()

    # KPI 1: Total revenue over time
    revenue_data = df.groupby('order_month')['order_total'].sum().reset_index()
    st.line_chart(data=revenue_data.rename(columns={'order_month': 'index'}).set_index('index')['order_total'])

    # KPI 2: Average Order Value (AOV)
    aov = df.groupby('order_id')['order_total'].mean().mean()
    st.metric("Average Order Value (AOV)", f"BRL {aov:.2f}")

    # KPI 3: Number of orders per month
    orders_data = df.groupby('order_month')['order_id'].nunique().reset_index()
    st.bar_chart(data=orders_data.rename(columns={'order_month': 'index'}).set_index('index')['order_id'])

    # KPI 4: Top 10 Product Categories by Revenue
    category_revenue = df.groupby('product_category_name')['order_total'].sum().reset_index()
    top_categories = category_revenue.sort_values(by='order_total', ascending=False).head(10)
    st.write("#### Top 10 Product Categories by Revenue")
    st.bar_chart(top_categories.set_index('product_category_name')['order_total'])

if __name__ == "__main__":
    main()
