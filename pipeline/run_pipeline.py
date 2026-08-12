import pandas as pd

def main():
    df = pd.read_csv('data/orders.csv')
    
    print(f'Rows before cleaning: {len(df)}')
    
    # Sort by order_date before dropping duplicates to ensure deterministic selection
    df = df.sort_values(by='order_date')
    duplicate_transactions = df[df.duplicated(subset='transaction_id', keep='first')]
    if not duplicate_transactions.empty:
        print(f'Duplicate transactions found: \n{duplicate_transactions}')
    df = df.drop_duplicates(subset='transaction_id', keep='first')
    df = df.dropna(subset='price')
    
    print(f'Rows after cleaning: {len(df)}')
    
    df.to_csv('data/processed_orders.csv', index=False)
    print('Successfully wrote cleaned data to data/processed_orders.csv')

if __name__ == '__main__':
    main()