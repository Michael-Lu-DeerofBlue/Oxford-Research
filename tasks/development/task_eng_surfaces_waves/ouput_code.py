#!/usr/bin/env python
"""
This script reproduces the simulation results of Figure 1 in the article
"Surface Wave-Aerodynamic Roughness Length Model for Air-Sea Interactions"
(see Ayala et al. 2024  [oai_citation:0‡paper.pdf](file-service://file-BJYCQrwMeromtsx2V8Knf6)). It loads surface distribution data 
from .mat files (in folder "Surfaces/"), computes the roughness length I0 using 
a SWARL model–based iterative procedure, calculates the corresponding logarithmic 
velocity profiles, and plots:
  (a) velocity profiles for laboratory (“B”) cases,
  (b) velocity profiles for multiscale field (“Y” and “S”) cases, and 
  (c) surface elevation maps for two representative cases (B3 and Y1).
  
Make sure that the folder "Surfaces/" is in your working directory.
"""

import os
import glob
import numpy as np
import scipy.io
import matplotlib.pyplot as plt

# Define constants
kappa = 0.4            # von Kármán constant
tol = 1e-6             # tolerance for fixed-point iteration on Lambda
max_iter = 100         # maximum iterations

def compute_I0(matdata):
    """
    Given the loaded .mat file (as a dict), compute the roughness length I0
    using a simplified version of the SWARL model.
    
    The matdata is expected to contain the following keys:
      "amp"    : wave amplitude (assumed constant)
      "dt"     : time step between snapshots
      "eta_t1" : 2D array, surface elevation at time t1
      "eta_t2" : 2D array, surface elevation at time t2
      "h"      : boundary layer height
      "Lx"     : domain size in x
      "Ly"     : domain size in y
      "nx"     : number of grid points in x
      "ny"     : number of grid points in y
      "Ret"    : friction Reynolds number (u_star * h / nu)
      "u_star" : friction velocity
    """
    # Extract variables (squeeze in case they are arrays from MATLAB)
    amp    = float(np.squeeze(matdata["amp"]))
    dt     = float(np.squeeze(matdata["dt"]))
    eta1   = np.squeeze(matdata["eta_t1"])
    eta2   = np.squeeze(matdata["eta_t2"])
    h      = float(np.squeeze(matdata["h"]))
    Lx     = float(np.squeeze(matdata["Lx"]))
    Ly     = float(np.squeeze(matdata["Ly"]))
    nx     = int(np.squeeze(matdata["nx"]))
    ny     = int(np.squeeze(matdata["ny"]))
    Ret    = float(np.squeeze(matdata["Ret"]))
    u_star = float(np.squeeze(matdata["u_star"]))
    
    # Compute kinematic viscosity from Ret = u_star * h / nu  => nu = u_star * h / Ret
    nu = u_star * h / Ret

    # Compute dominant positive height:
    eta_mean = np.mean(eta1)
    eta_prime = eta1 - eta_mean
    # Only consider positive deviations
    pos_dev = eta_prime[eta_prime > 0]
    if pos_dev.size == 0:
        h_dom = 0.0
    else:
        h_dom = np.mean(pos_dev)
    # Set reference height Δ = 3 * dominant height
    Delta = 3.0 * h_dom
    if Delta <= 0:
        # In case the field has zero or negative dominant height,
        # choose a small Delta (avoid division by zero later)
        Delta = 1e-3

    # Compute Δ⁺ = Delta * u_star/nu
    Delta_plus = Delta * u_star / nu

    # Compute friction factor for smooth surface (f5B)
    f5B = 0.0288 * (Delta_plus)**(-1/5) * (1 + 577*(Delta_plus)**(-6/5))**(2/3)
    # For a smooth resolved surface, we set f5 = f5B (since the subgrid term vanishes)
    f5 = f5B

    # Compute grid spacings (assume uniform grid)
    dx = Lx / nx
    dy = Ly / ny

    # Compute spatial gradients using first-order finite differences:
    # Note: np.gradient uses central differences in the interior.
    grad_y, grad_x = np.gradient(eta1, dy, dx)  # grad_y along axis0, grad_x along axis1
    grad_mag = np.sqrt(grad_x**2 + grad_y**2)

    # Compute vertical derivative from the two snapshots (deta/dt)
    deta_dt = (eta2 - eta1) / dt

    # Compute local phase speed (avoid division by very small gradients)
    eps = 1e-8
    c_local = np.abs(deta_dt) / (grad_mag + eps)
    # Use only points with significant gradients to compute a representative phase speed
    valid = grad_mag > 1e-5
    if np.any(valid):
        c_avg = np.median(c_local[valid])
    else:
        c_avg = np.median(c_local)
    # Ensure c_avg is positive
    c_avg = max(c_avg, 1e-3)

    # Solve for Lambda (Λ) using fixed-point iteration on the simplified Eq. (10):
    #   Λ = (amp²/(4*c_avg))*(1 - sqrt(Λ))² + 0.5*f5
    Lambda = 1.0  # initial guess
    for it in range(max_iter):
        Lambda_new = (amp**2/(4*c_avg)) * (1 - np.sqrt(Lambda))**2 + 0.5*f5
        if np.abs(Lambda_new - Lambda) < tol * Lambda:
            Lambda = Lambda_new
            break
        Lambda = Lambda_new
    else:
        print("Warning: Lambda did not converge within max_iter.")

    # Compute the roughness length: I0 = Delta * exp( - kappa / sqrt(Lambda) )
    I0 = Delta * np.exp(- kappa * (Lambda)**(-0.5))
    
    return I0, Delta, c_avg, u_star, h

def compute_velocity_profile(I0, u_star, z):
    """
    Compute the logarithmic velocity profile: 
         u(z) = (u_star/κ) * ln(z/I0)
    """
    return (u_star / kappa) * np.log(z / I0)

def load_cases():
    """
    Load all .mat files from the "Surfaces/" folder and group them according
    to filename (here we assume the case names start with a letter such as B, Y, S, etc.).
    Returns a dict mapping group names to a list of case names, a dict mapping case names 
    to their computed velocity profile data, and a dict for cases to be used for surface 
    visualization.
    """
    cases = {}
    surf_cases = {}  # for surface elevation plots (e.g. B3 and Y1)
    folder = "Surfaces"
    file_list = glob.glob(os.path.join(folder, "*.mat"))
    
    # For storing velocity profile data for each case
    profile_data = {}
    
    for fpath in file_list:
        case_name = os.path.splitext(os.path.basename(fpath))[0]
        # load .mat file
        matdata = scipy.io.loadmat(fpath)
        I0, Delta, c_avg, u_star, h = compute_I0(matdata)
        # Create a vertical grid from slightly above I0 to h (or 10 m if h is very high)
        z_min = I0 * 1.01
        z_max = min(h, 10.0)
        z = np.linspace(z_min, z_max, 100)
        u_profile = compute_velocity_profile(I0, u_star, z)
        profile_data[case_name] = (z, u_profile)
        
        # Group cases by first letter of case_name (e.g., "B", "Y", "S")
        key = case_name[0].upper()
        if key not in cases:
            cases[key] = []
        cases[key].append(case_name)
        
        # Also store cases for surface plots (here we select B3 and Y1)
        if case_name in ["B3", "Y1"]:
            surf_cases[case_name] = (matdata, I0)
            
    return cases, profile_data, surf_cases

def plot_results(cases, profile_data, surf_cases):
    """
    Create a figure with three panels:
      (a) velocity profiles for cases with key "B" (lab cases)
      (b) velocity profiles for cases with key "Y" or "S" (multiscale field cases)
      (c) surface elevation maps for two representative cases (B3 and Y1)
    """
    fig = plt.figure(figsize=(12, 10))
    
    # Panel (a): velocity profiles for "B" cases
    ax1 = fig.add_subplot(2,2,1)
    if "B" in cases:
        for case in cases["B"]:
            z, u_prof = profile_data[case]
            ax1.plot(u_prof, z, label=case)
        ax1.set_xlabel("u (m/s)")
        ax1.set_ylabel("z (m)")
        ax1.set_title("Mean Velocity Profiles (Lab cases: B1–B5)")
        ax1.legend()
    else:
        ax1.text(0.5, 0.5, "No B cases found", ha="center")
    
    # Panel (b): velocity profiles for "Y" and "S" cases
    ax2 = fig.add_subplot(2,2,2)
    keys = []
    if "Y" in cases:
        keys.append("Y")
    if "S" in cases:
        keys.append("S")
    if keys:
        for key in keys:
            for case in cases[key]:
                z, u_prof = profile_data[case]
                ax2.plot(u_prof, z, label=case)
        ax2.set_xlabel("u (m/s)")
        ax2.set_ylabel("z (m)")
        ax2.set_title("Mean Velocity Profiles (Field cases: Y and S)")
        ax2.legend()
    else:
        ax2.text(0.5, 0.5, "No Y/S cases found", ha="center")
    
    # Panel (c): surface elevation maps for two representative cases (B3 and Y1)
    # Plotting them side by side
    if "B3" in surf_cases:
        matdata_B3, I0_B3 = surf_cases["B3"]
        eta_B3 = np.squeeze(matdata_B3["eta_t1"])
        Lx = float(np.squeeze(matdata_B3["Lx"]))
        Ly = float(np.squeeze(matdata_B3["Ly"]))
        ax3 = fig.add_subplot(2,2,3)
        im1 = ax3.imshow(eta_B3, extent=[0, Lx, 0, Ly], origin="lower", cmap="viridis")
        ax3.set_title("Surface Elevation Map (B3)")
        ax3.set_xlabel("x (m)")
        ax3.set_ylabel("y (m)")
        fig.colorbar(im1, ax=ax3, shrink=0.8)
    else:
        ax3 = fig.add_subplot(2,2,3)
        ax3.text(0.5, 0.5, "B3 case not found", ha="center")
    
    if "Y1" in surf_cases:
        matdata_Y1, I0_Y1 = surf_cases["Y1"]
        eta_Y1 = np.squeeze(matdata_Y1["eta_t1"])
        Lx = float(np.squeeze(matdata_Y1["Lx"]))
        Ly = float(np.squeeze(matdata_Y1["Ly"]))
        ax4 = fig.add_subplot(2,2,4)
        im2 = ax4.imshow(eta_Y1, extent=[0, Lx, 0, Ly], origin="lower", cmap="viridis")
        ax4.set_title("Surface Elevation Map (Y1)")
        ax4.set_xlabel("x (m)")
        ax4.set_ylabel("y (m)")
        fig.colorbar(im2, ax=ax4, shrink=0.8)
    else:
        ax4 = fig.add_subplot(2,2,4)
        ax4.text(0.5, 0.5, "Y1 case not found", ha="center")
    
    fig.suptitle("Reproduced Simulation Results (Figure 1)", fontsize=16)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    plt.show()

def main():
    cases, profile_data, surf_cases = load_cases()
    plot_results(cases, profile_data, surf_cases)

if __name__ == "__main__":
    main()