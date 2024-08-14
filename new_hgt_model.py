import torch
import torch.nn.functional as F
from torch_geometric.data import Data
import pandas as pd
from sklearn.preprocessing import LabelEncoder

# Custom HGT Layer (Simplified to only handle node types)
class CustomHGTLayer(torch.nn.Module):
    def __init__(self, in_channels, out_channels):
        super(CustomHGTLayer, self).__init__()
        self.linear = torch.nn.Linear(in_channels, out_channels)

    def forward(self, x, edge_index):
        # Simple message passing using the linear transformation
        return F.relu(self.linear(x))

# Function to load and preprocess data
def load_data(node_path, edge_path):
    nodes = pd.read_csv(node_path)
    edges = pd.read_csv(edge_path)

    # Ensure IDs are consistent and strip any whitespace
    nodes['user_id'] = nodes['user_id'].astype(str).str.strip()
    edges['source_id'] = edges['source_id'].astype(str).str.strip()
    edges['target_id'] = edges['target_id'].astype(str).str.strip()

    # Debugging: Print the unique values to ensure they match
    print("Unique user_ids in nodes:", sorted(nodes['user_id'].unique()))
    print("Unique source_ids in edges:", sorted(edges['source_id'].unique()))
    print("Unique target_ids in edges:", sorted(edges['target_id'].unique()))

    # Ensure that all source and target nodes are in the nodes dataset
    node_ids = set(nodes['user_id'])
    edge_source_ids = set(edges['source_id'])
    edge_target_ids = set(edges['target_id'])

    # Filter edges to only include those where both source and target are in the nodes dataset
    valid_edges = edges[edges['source_id'].isin(node_ids) & edges['target_id'].isin(node_ids)]
    
    if len(valid_edges) != len(edges):
        print(f"Skipping {len(edges) - len(valid_edges)} edges due to missing nodes.")

    return nodes, valid_edges

def preprocess(nodes, edges):
    # Convert categorical columns to strings for encoding
    nodes = nodes.astype(str)
    edges = edges.astype(str)
    
    return nodes, edges

def encode_data(nodes, edges):
    # Directly compare IDs before encoding
    print("Direct comparison of IDs in nodes and edges:")
    print("Source IDs in edges not in nodes:", set(edges['source_id']) - set(nodes['user_id']))
    print("Target IDs in edges not in nodes:", set(edges['target_id']) - set(nodes['user_id']))

    # Create mapping from user_id to a numeric index
    user_id_encoder = LabelEncoder()
    
    # Explicitly fit the encoder on the node IDs
    user_id_encoder.fit(nodes['user_id'])

    # Encode node IDs
    nodes['user_idx'] = user_id_encoder.transform(nodes['user_id'])

    # Map edges to node indices using the same encoder
    edges['source_idx'] = user_id_encoder.transform(edges['source_id'])
    edges['target_idx'] = user_id_encoder.transform(edges['target_id'])

    # Encode other categorical variables in nodes and edges
    encoders = {}
    for col in nodes.columns:
        if col != 'user_id' and nodes[col].dtype == 'object':
            encoder = LabelEncoder()
            nodes[col] = encoder.fit_transform(nodes[col])
            encoders[col] = encoder

    for col in edges.columns:
        if col not in ['source_id', 'target_id', 'source_idx', 'target_idx'] and edges[col].dtype == 'object':
            encoder = LabelEncoder()
            edges[col] = encoder.fit_transform(edges[col])
            encoders[col] = encoder

    return nodes, edges, encoders

class CustomHGTModel(torch.nn.Module):
    def __init__(self, in_channels, hidden_channels, out_channels, num_node_types):
        super(CustomHGTModel, self).__init__()
        self.node_type_embedding = torch.nn.Embedding(num_node_types, hidden_channels)

        self.layer1 = CustomHGTLayer(in_channels, hidden_channels)
        self.layer2 = CustomHGTLayer(hidden_channels, out_channels)

    def forward(self, x, edge_index):
        x = F.relu(self.layer1(x, edge_index))
        x = F.relu(self.layer2(x, edge_index))
        return x

def train_model(model, data, epochs=10, lr=0.001):
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    model.train()

    # Debugging: Check if data.y exists and is valid
    if data.y is None:
        raise ValueError("Target data (y) is missing from the dataset.")

    for epoch in range(epochs):
        optimizer.zero_grad()
        out = model(data.x, data.edge_index)
        loss = F.mse_loss(out, data.y)
        loss.backward()
        optimizer.step()
        print(f'Epoch {epoch+1}, Loss: {loss.item()}')

    return model

def main():
    # Paths to the data
    node_path = './gnn_sampledata/nodes.csv'
    edge_path = './gnn_sampledata/edges.csv'

    # Load and preprocess the data
    nodes, edges = load_data(node_path, edge_path)
    nodes, edges = preprocess(nodes, edges)
    
    try:
        nodes, edges, encoders = encode_data(nodes, edges)
    except ValueError as e:
        print(f"Error during encoding: {e}")
        return

    # Prepare data for PyTorch Geometric
    node_features = torch.tensor(nodes.drop(columns=['user_id', 'user_idx']).values, dtype=torch.float)
    edge_index = torch.tensor([edges['source_idx'].values, edges['target_idx'].values], dtype=torch.long)
    
    # Debugging: Check if node_features and edge_index are correct
    print(f"Node features shape: {node_features.shape}")
    print(f"Edge index shape: {edge_index.shape}")

    # Assuming 'reported_risk' as the target
    y = torch.tensor(nodes['reported_risk'].values, dtype=torch.float).view(-1, 1)

    data = Data(
        x=node_features,
        edge_index=edge_index,
        y=y
    )

    # Initialize the custom HGT model
    num_node_types = 1  # Assuming all nodes are of a single type
    model = CustomHGTModel(in_channels=node_features.shape[1], hidden_channels=32, out_channels=64, num_node_types=num_node_types)

    # Train the model
    trained_model = train_model(model, data, epochs=10, lr=0.001)

    # Generate embeddings
    embeddings = trained_model(data.x, data.edge_index)
    print("Node embeddings:", embeddings)

if __name__ == "__main__":
    main()
 #