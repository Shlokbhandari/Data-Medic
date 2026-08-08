import pandas as pd

def main():
    df_in = pd.read_csv('data/orders_broken.csv')
    print(f"Rows before cleaning: {len(df_in)}")

    df_out = df_in.drop_duplicates(subset=['transaction_id'])
    df_out = df_out.dropna(subset=['price'])
    
    print(f"Rows after cleaning: {len(df_out)}")

    dropped_df = df_in[~df_in.index.isin(df_out.index)]
    
    if not dropped_df.empty:
        print("\nRows dropped silently:")
        for idx, row in dropped_df.iterrows():
            reasons = []
            if pd.isna(row['price']):
                reasons.append("Missing price")
            if df_in.duplicated(subset=['transaction_id'], keep='first').loc[idx]:
                reasons.append(f"Duplicate transaction_id ({row['transaction_id']})")
                
            print(f"- Order ID {row['order_id']}: {', '.join(reasons)}")
    else:
        print("\nNo rows dropped.")

if __name__ == "__main__":
    main()
