import pandas as pd

def main():
    df = pd.read_csv('data/orders.csv')
    
    print(f'Rows before cleaning: {len(df)}')

    df = df.drop_duplicates(subset=['transaction_id'])
    df = df.dropna(subset=['price'])
    
    # Isolate rows with price == 0.0
    flagged_rows = df[df['price'] == 0.0]
    if not flagged_rows.empty:
        flagged_rows.to_csv('data/flagged_orders.csv', index=False)
        print(f'Flagged {len(flagged_rows)} row(s) with price == 0.0 and wrote to data/flagged_orders.csv')
    
    # Exclude flagged rows from the main DataFrame
    df = df[df['price'] != 0.0]
    
    print(f'Rows after cleaning: {len(df)}')

    df.to_csv('data/processed_orders.csv', index=False)
    print('Successfully wrote cleaned data to data/processed_orders.csv')

if __name__ == '__main__':
    main()