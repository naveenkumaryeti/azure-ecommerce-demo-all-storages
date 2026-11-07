#!/usr/bin/env bash
export MSYS_NO_PATHCONV=1
# Shared parameters. Override by exporting before running, e.g.  RG=my-rg LOCATION=southindia ./deploy.sh
export RG="${RG:-rg-ecommerce-demo}"
export LOCATION="${LOCATION:-centralindia}"
export VM_SIZE="${VM_SIZE:-Standard_DC1s_v3}"
export BACKEND_ILB_IP="${BACKEND_ILB_IP:-10.20.2.10}"
# Storage names are global + 3-24 lowercase chars: derive a stable one from subscription + RG
export STORAGE_NAME="${STORAGE_NAME:-ecom$(echo -n "$(az account show --query id -o tsv 2>/dev/null)$RG" | md5sum | cut -c1-12)}"
export BACKEND_VMSS=backend-vmss FRONTEND_VMSS=frontend-vmss VNET=ecommerce-vnet
export ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fe_ip() { az network public-ip show -g "$RG" -n frontend-vmss-lb-pip --query ipAddress -o tsv; }

# Windows (Git Bash): convert MSYS paths (/tmp, /c/...) to C:/... for native Windows programs (az, python). No-op on Linux/macOS/WSL.
W() { if command -v cygpath >/dev/null 2>&1; then cygpath -m "$1"; else echo "$1"; fi; }
