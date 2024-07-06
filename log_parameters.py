import numpy as np
import pandas as pd
import torch
import string
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset

from tqdm import tqdm

import matplotlib.pyplot as plt
from glob_inc.utils import *
import logging
import torch.nn.functional as F
from torch.utils.data import DataLoader
from torchvision import datasets, transforms
from cifar import CNNCifar, get_cifar10, cifar10_noniid_lt, get_data_loaders

# Cấu hình logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
NUM_DEVICE = 2
def evaluate_model(model, test_loader, criterion):
    model.eval()
    test_loss = 0
    correct = 0
    with torch.no_grad():
        for data, target in test_loader:
            data, target = data.to(device), target.to(device)
            output, _ = model(data)
            test_loss += criterion(output, target).item()
            pred = output.argmax(dim=1, keepdim=True)
            correct += pred.eq(target.view_as(pred)).sum().item()
    test_loss /= len(test_loader.dataset)
    accuracy = 100. * correct / len(test_loader.dataset)
    return test_loss, accuracy

def do_evaluate_round():
    learning_rate = 0.001
    rounds = 3  # Số vòng lặp đánh giá mô hình
    model_path = "saved_model/CifarModel.pt"
    round_dict = {}

    train_loader, test_loader, _, train_dataset = get_cifar10()
    dict_users = cifar10_noniid_lt(train_dataset, NUM_DEVICE)
    user_data_loaders = get_data_loaders(train_dataset, dict_users)
    
    model = CNNCifar().to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    criterion = torch.nn.CrossEntropyLoss()

    # Tải mô hình đã lưu
    checkpoint = torch.load(model_path)
    model.load_state_dict(checkpoint['model_state_dict'])
    optimizer.load_state_dict(checkpoint['optimizer_state_dict'])

    for rnd in range(1, rounds + 1):
        # Đánh giá mô hình sau mỗi vòng
        test_loss, accuracy = evaluate_model(model, test_loader, criterion)
        logger.info(f'Round: {rnd}, Test Loss: {test_loss:.4f}, Accuracy: {accuracy:.3f}%')

        round_dict[f"round_{rnd}"] = {"eval_loss": test_loss, "accuracy": accuracy}

        # Training logic ở đây (nếu cần thiết) cho mỗi vòng
        model.train()
        for user_loader in user_data_loaders:
            for batch_idx, (data, target) in enumerate(user_loader):
                data, target = data.to(device), target.to(device)
                output, protos = model(data)
                loss = criterion(output, target)
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()

    return round_dict

if __name__ == "__main__":
    NUM_ROUNDS = 3
    ROUND_DICT = do_evaluate_round()

    # Extract accuracy and avg_loss values from round_dict
    accuracies = [ROUND_DICT[f"round_{i+1}"]["accuracy"] for i in range(NUM_ROUNDS)]
    avg_losses = [ROUND_DICT[f"round_{i+1}"]["eval_loss"] for i in range(NUM_ROUNDS)]

    # Create a figure with two subplots
    fig, axs = plt.subplots(1, 2, figsize=(15, 5))

    # Plot accuracy
    axs[0].plot(range(1, NUM_ROUNDS + 1), accuracies, marker='o')
    axs[0].set_title('Accuracy over rounds')
    axs[0].set_xlabel('Round')
    axs[0].set_ylabel('Accuracy (%)')
    axs[0].set_xticks(range(1, NUM_ROUNDS + 1))
    axs[0].grid(True)

    # Plot average loss
    axs[1].plot(range(1, NUM_ROUNDS + 1), avg_losses, marker='o', color='red')
    axs[1].set_title('Average Loss over rounds')
    axs[1].set_xlabel('Round')
    axs[1].set_ylabel('Average Loss')
    axs[1].set_xticks(range(1, NUM_ROUNDS + 1))
    axs[1].grid(True)

    plt.tight_layout()
    plt.savefig('metrics.png')
    plt.show()
