from typing import *
import numpy as np
import torch
from torch import nn
from omegaconf.listconfig import ListConfig
from torch_points3d.modules.EMHS.modules import EMHSLayer
from torch_points3d.utils.enums import AttentionType


class Inputs(NamedTuple):
    x: torch.Tensor
    consecutive_cluster: torch.Tensor
    cluster_non_consecutive: torch.Tensor
    batch: torch.Tensor


class EMHSModel(nn.Module):
    def __init__(
        self,
        input_nc: int = None,
        output_nc: int = None,
        num_layers: int = 56,
        num_elm: int = 2,
        use_attention: bool = True,
        layers_slice: List = None,
        latent_classes: List = None,
        voxelization: List = [9, 9, 9],
        kernel_size: List = [3, 3, 3],
        feat_dim: int = 64,
        attention_type: str = AttentionType.CLL.value,
    ):

        assert input_nc is not None, "input_nc is undefined"
        assert output_nc is not None, "output_nc is undefined"
        assert layers_slice is not None, "layers_slice is undefined"
        if use_attention:
            assert latent_classes is not None, "latent_classes is undefined"
            assert len(latent_classes) + 1 == len(
                layers_slice
            ), "latent_classes and layers_slice should have the same size"
        self._voxelization = voxelization.to_container() if isinstance(voxelization, ListConfig) else voxelization

        # VALIDATION FOR IDX SLICES
        layers_idx = []
        for idx_ls in range(len(layers_slice) - 1):
            s, e = layers_slice[idx_ls], layers_slice[idx_ls + 1]
            for layer_idx in range(int(s), int(e)):
                layers_idx.append(layer_idx)
        assert len(np.unique(layers_idx)) == num_layers, (len(np.unique(layers_idx)), num_layers)

        super().__init__()

        for idx_ls in range(len(layers_slice) - 1):
            s, e = layers_slice[idx_ls], layers_slice[idx_ls + 1]
            for layer_idx in range(int(s), int(e)):
                is_first = layer_idx == min(layers_idx)
                is_last = layer_idx == max(layers_idx)
                module = EMHSLayer(
                    input_nc if is_first else feat_dim,
                    output_nc if is_last else feat_dim,
                    feat_dim,
                    num_elm,
                    use_attention if not is_last else False,
                    latent_classes[idx_ls] if latent_classes is not None else None,
                    kernel_size,
                    voxelization,
                    attention_type,
                )
                self.add_module(str(layer_idx), module)

    @property
    def voxelization(self):
        return self._voxelization

    def forward(self, x, consecutive_cluster, cluster_non_consecutive, batch=None):
        unique_cluster_non_consecutive = torch.unique(cluster_non_consecutive)
        if batch is not None:
            batch_size = len(torch.unique(batch))
        else:
            batch_size = x.shape[0]
        for m in self._modules.values():
            x = m(
                x,
                consecutive_cluster,
                cluster_non_consecutive,
                unique_cluster_non_consecutive,
                batch=batch,
                batch_size=batch_size,
            )
        return x