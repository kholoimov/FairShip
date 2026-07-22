// SPDX-License-Identifier: LGPL-3.0-or-later
// SPDX-FileCopyrightText: Copyright CERN for the benefit of the SHiP
// Collaboration

#include "EvtCalcGenerator.h"

#include <cmath>
#include <stdexcept>
#include <string>

#include "FairLogger.h"
#include "FairPrimaryGenerator.h"
#include "ShipUnit.h"
#include "TDatabasePDG.h"
#include "TFile.h"
#include "TMath.h"

// -----   Default constructor   -------------------------------------------
EvtCalcGenerator::EvtCalcGenerator() = default;
// -------------------------------------------------------------------------
// -----   Default constructor   -------------------------------------------
Bool_t EvtCalcGenerator::Init(const char* fileName) {
  return Init(fileName, 0);
}
// -----   Default constructor   -------------------------------------------
Bool_t EvtCalcGenerator::Init(const char* fileName, const int startEvent) {
  if (startEvent < 0) {
    LOG(error) << "EvtCalcGenerator: startEvent must be >= 0, got "
               << startEvent;
    return kFALSE;
  }
  fTree.reset();
  fInputFile.reset();
  branchVars.clear();
  fDaughterPx = nullptr;
  fDaughterPy = nullptr;
  fDaughterPz = nullptr;
  fDaughterE = nullptr;
  fDaughterMass = nullptr;
  fDaughterPdg = nullptr;
  fInputFile = std::unique_ptr<TFile>(TFile::Open(fileName, "read"));
  LOGF(info, "Info EvtCalcGenerator: Opening input file %s", fileName);
  if (!fInputFile || fInputFile->IsZombie()) {
    LOG(error) << "EvtCalcGenerator: error opening input file " << fileName;
    fInputFile.reset();
    return kFALSE;
  }

  auto* inputTree = dynamic_cast<TTree*>(fInputFile->Get("LLP_tree"));
  if (inputTree != nullptr) {
    fInputFormat = InputFormat::FlatBranches;
  } else {
    inputTree = dynamic_cast<TTree*>(fInputFile->Get("Events"));
    fInputFormat = InputFormat::VectorBranches;
  }
  fTree = std::unique_ptr<TTree>(inputTree);
  if (!fTree) {
    LOG(error) << "EvtCalcGenerator: cannot find tree LLP_tree or Events in "
               << fileName;
    fInputFile.reset();
    return kFALSE;
  }
  fNevents = fTree->GetEntries();
  if (startEvent >= fNevents) {
    LOG(error) << "EvtCalcGenerator: startEvent " << startEvent
               << " is out of range for " << fNevents << " entries";
    fTree.reset();
    fInputFile.reset();
    return kFALSE;
  }
  fn = startEvent;

  const Bool_t branchesBound = fInputFormat == InputFormat::FlatBranches
                                   ? BindFlatBranches()
                                   : BindVectorBranches();
  if (!branchesBound) {
    fTree.reset();
    fInputFile.reset();
    return kFALSE;
  }

  LOG(info) << "EvtCalcGenerator: using "
            << (fInputFormat == InputFormat::FlatBranches
                    ? "LLP_tree flat-branch"
                    : "Events vector-daughter")
            << " input schema";
  return kTRUE;
}

Bool_t EvtCalcGenerator::BindFlatBranches() {
  auto* branches = fTree->GetListOfBranches();
  if (!branches) {
    LOG(error) << "EvtCalcGenerator: failed to access tree branches";
    return kFALSE;
  }
  nBranches = branches->GetEntries();
  if (nBranches <= 0) {
    LOG(error) << "EvtCalcGenerator: tree LLP_tree has no branches";
    return kFALSE;
  }
  branchVars.resize(nBranches);

  for (int i = 0; i < nBranches; ++i) {
    auto* branch = dynamic_cast<TBranch*>(branches->At(i));
    if (!branch) {
      LOG(error) << "EvtCalcGenerator: encountered an invalid branch entry";
      return kFALSE;
    }
    if (fTree->FindBranch(branch->GetName())) {
      if (fTree->SetBranchAddress(branch->GetName(), &branchVars[i]) < 0) {
        LOG(error) << "EvtCalcGenerator: failed to bind branch "
                   << branch->GetName();
        return kFALSE;
      }
    }
  }

  return kTRUE;
}

Bool_t EvtCalcGenerator::BindVectorBranches() {
  const std::vector<std::string> requiredBranches = {
      "LLP_px",     "LLP_py", "LLP_pz", "LLP_E", "LLP_m", "LLP_pdg",
      "LLP_weight", "vtx_x",  "vtx_y",  "vtx_z", "d_px",  "d_py",
      "d_pz",       "d_E",    "d_m",    "d_pdg"};
  for (const auto& branchName : requiredBranches) {
    if (fTree->GetBranch(branchName.c_str()) == nullptr) {
      LOG(error) << "EvtCalcGenerator: Events tree is missing required branch "
                 << branchName;
      return kFALSE;
    }
  }

  bool success = true;
  success &= fTree->SetBranchAddress("LLP_px", &fMotherPx) >= 0;
  success &= fTree->SetBranchAddress("LLP_py", &fMotherPy) >= 0;
  success &= fTree->SetBranchAddress("LLP_pz", &fMotherPz) >= 0;
  success &= fTree->SetBranchAddress("LLP_E", &fMotherE) >= 0;
  success &= fTree->SetBranchAddress("LLP_m", &fMotherMass) >= 0;
  success &= fTree->SetBranchAddress("LLP_pdg", &fMotherPdg) >= 0;
  success &= fTree->SetBranchAddress("LLP_weight", &fDecayProbability) >= 0;
  success &= fTree->SetBranchAddress("vtx_x", &fVertexX) >= 0;
  success &= fTree->SetBranchAddress("vtx_y", &fVertexY) >= 0;
  success &= fTree->SetBranchAddress("vtx_z", &fVertexZ) >= 0;
  success &= fTree->SetBranchAddress("d_px", &fDaughterPx) >= 0;
  success &= fTree->SetBranchAddress("d_py", &fDaughterPy) >= 0;
  success &= fTree->SetBranchAddress("d_pz", &fDaughterPz) >= 0;
  success &= fTree->SetBranchAddress("d_E", &fDaughterE) >= 0;
  success &= fTree->SetBranchAddress("d_m", &fDaughterMass) >= 0;
  success &= fTree->SetBranchAddress("d_pdg", &fDaughterPdg) >= 0;
  if (!success) {
    LOG(error) << "EvtCalcGenerator: failed to bind one or more branches in "
                  "the Events tree";
    return kFALSE;
  }
  return kTRUE;
}

Bool_t EvtCalcGenerator::ValidateVectorDaughters() const {
  if (fDaughterPx == nullptr || fDaughterPy == nullptr ||
      fDaughterPz == nullptr || fDaughterE == nullptr ||
      fDaughterMass == nullptr || fDaughterPdg == nullptr) {
    LOG(error) << "EvtCalcGenerator: null daughter vector in Events tree";
    return kFALSE;
  }
  const auto size = fDaughterPx->size();
  if (fDaughterPy->size() != size || fDaughterPz->size() != size ||
      fDaughterE->size() != size || fDaughterMass->size() != size ||
      fDaughterPdg->size() != size) {
    LOG(error) << "EvtCalcGenerator: inconsistent daughter vector sizes in "
                  "Events tree entry "
               << fn;
    return kFALSE;
  }
  return kTRUE;
}
// -----   Destructor   ----------------------------------------------------
EvtCalcGenerator::~EvtCalcGenerator() = default;

// -- Generalized branch access --------------------------------------------
Double_t EvtCalcGenerator::GetBranchValue(const std::unique_ptr<TTree>& tree,
                                          unsigned index) const {
  if (index < branchVars.size()) {
    return branchVars[index];
  } else {
    throw std::out_of_range("Branch index out of range");
  }
}
// -- Generalized daughter variable access ---------------------------------
Double_t EvtCalcGenerator::GetDaughterValue(const std::unique_ptr<TTree>& tree,
                                            int dauID, int offset) const {
  int baseIndex = 10 + (dauID * 6);
  return GetBranchValue(tree, baseIndex + offset);
}

// -- Wrapper functions ----------------------------------------------------
// -------------------------------------------------------------------------
Double_t EvtCalcGenerator::GetNdaughters(
    const std::unique_ptr<TTree>& tree) const {
  if (fInputFormat == InputFormat::VectorBranches) {
    return static_cast<Double_t>(fDaughterPx->size());
  }
  return GetBranchValue(tree, nBranches - 1);
}

// -- LLP properties ------------------------------------------------------
Double_t EvtCalcGenerator::GetMotherPx(
    const std::unique_ptr<TTree>& tree) const {
  if (fInputFormat == InputFormat::VectorBranches) return fMotherPx;
  return GetBranchValue(tree, static_cast<int>(BranchIndices::MotherPx));
}
Double_t EvtCalcGenerator::GetMotherPy(
    const std::unique_ptr<TTree>& tree) const {
  if (fInputFormat == InputFormat::VectorBranches) return fMotherPy;
  return GetBranchValue(tree, static_cast<int>(BranchIndices::MotherPy));
}
Double_t EvtCalcGenerator::GetMotherPz(
    const std::unique_ptr<TTree>& tree) const {
  if (fInputFormat == InputFormat::VectorBranches) return fMotherPz;
  return GetBranchValue(tree, static_cast<int>(BranchIndices::MotherPz));
}
Double_t EvtCalcGenerator::GetMotherE(
    const std::unique_ptr<TTree>& tree) const {
  if (fInputFormat == InputFormat::VectorBranches) return fMotherE;
  return GetBranchValue(tree, static_cast<int>(BranchIndices::MotherE));
}

// -- Vertex properties ---------------------------------------------------
Double_t EvtCalcGenerator::GetVx(const std::unique_ptr<TTree>& tree) const {
  if (fInputFormat == InputFormat::VectorBranches) return fVertexX;
  return GetBranchValue(tree, static_cast<int>(BranchIndices::Vx));
}
Double_t EvtCalcGenerator::GetVy(const std::unique_ptr<TTree>& tree) const {
  if (fInputFormat == InputFormat::VectorBranches) return fVertexY;
  return GetBranchValue(tree, static_cast<int>(BranchIndices::Vy));
}
Double_t EvtCalcGenerator::GetVz(const std::unique_ptr<TTree>& tree) const {
  if (fInputFormat == InputFormat::VectorBranches) return fVertexZ;
  return GetBranchValue(tree, static_cast<int>(BranchIndices::Vz));
}

// -- Decay probability ---------------------------------------------------
Double_t EvtCalcGenerator::GetDecayProb(
    const std::unique_ptr<TTree>& tree) const {
  if (fInputFormat == InputFormat::VectorBranches) return fDecayProbability;
  return GetBranchValue(tree, static_cast<int>(BranchIndices::DecayProb));
}

// -- Daughter properties ------------------------------------------------
Double_t EvtCalcGenerator::GetDauPx(const std::unique_ptr<TTree>& tree,
                                    int dauID) const {
  if (fInputFormat == InputFormat::VectorBranches) {
    return fDaughterPx->at(dauID);
  }
  return GetDaughterValue(tree, dauID, 0);
}
Double_t EvtCalcGenerator::GetDauPy(const std::unique_ptr<TTree>& tree,
                                    int dauID) const {
  if (fInputFormat == InputFormat::VectorBranches) {
    return fDaughterPy->at(dauID);
  }
  return GetDaughterValue(tree, dauID, 1);
}
Double_t EvtCalcGenerator::GetDauPz(const std::unique_ptr<TTree>& tree,
                                    int dauID) const {
  if (fInputFormat == InputFormat::VectorBranches) {
    return fDaughterPz->at(dauID);
  }
  return GetDaughterValue(tree, dauID, 2);
}
Double_t EvtCalcGenerator::GetDauE(const std::unique_ptr<TTree>& tree,
                                   int dauID) const {
  if (fInputFormat == InputFormat::VectorBranches) {
    return fDaughterE->at(dauID);
  }
  return GetDaughterValue(tree, dauID, 3);
}
Double_t EvtCalcGenerator::GetDauPDG(const std::unique_ptr<TTree>& tree,
                                     int dauID) const {
  if (fInputFormat == InputFormat::VectorBranches) {
    return fDaughterPdg->at(dauID);
  }
  return GetDaughterValue(tree, dauID, 5);
}

// -----   Passing the event   -------------------------------------------
Bool_t EvtCalcGenerator::ReadEvent(FairPrimaryGenerator* cpg) {
  if (fn >= fNevents) {
    LOG(warning) << "End of input file. Rewind.";
    fn = 0;
  }

  if (fTree->GetEntry(fn) <= 0) {
    LOG(error) << "EvtCalcGenerator: failed to read input entry " << fn;
    return kFALSE;
  }
  if (fInputFormat == InputFormat::VectorBranches &&
      !ValidateVectorDaughters()) {
    return kFALSE;
  }
  fn++;
  if (fn % 100 == 0) LOGF(info, "Info EvtCalcGenerator: event nr %d", fn);

  Ndau = GetNdaughters(fTree);
  // Vertex coordinates in the SHiP reference frame, expressed in [cm]
  Double_t space_unit_conv = 100.;                                    // m to cm
  Double_t coord_shift = (zDecayVolume - ztarget) / space_unit_conv;  // units m
  Double_t vx_transf = GetVx(fTree) * space_unit_conv;  // units cm
  Double_t vy_transf = GetVy(fTree) * space_unit_conv;  // units cm
  Double_t vz_transf =
      (GetVz(fTree) - coord_shift) * space_unit_conv;  // units cm

  Double_t c = 2.99792458e+10;  // speed of light [cm/s]
  Double_t tof = TMath::Sqrt(vx_transf * vx_transf + vy_transf * vy_transf +
                             vz_transf * vz_transf) /
                 c;
  Double_t decay_prob = GetDecayProb(fTree);
  Double_t pdg_dau = 0;

  // Mother LLP
  Bool_t wanttracking = false;
  Double_t pdg_llp = 999;  // Geantino, placeholder

  cpg->AddTrack(pdg_llp, GetMotherPx(fTree), GetMotherPy(fTree),
                GetMotherPz(fTree), vx_transf, vy_transf, vz_transf, -1.,
                wanttracking, GetMotherE(fTree), tof, decay_prob);

  wanttracking = true;

  // Secondaries
  for (int iPart = 0; iPart < Ndau; ++iPart) {
    pdg_dau = GetDauPDG(fTree, iPart);
    if (pdg_dau != -999) {
      cpg->AddTrack(pdg_dau, GetDauPx(fTree, iPart), GetDauPy(fTree, iPart),
                    GetDauPz(fTree, iPart), vx_transf, vy_transf, vz_transf, 0.,
                    wanttracking, GetDauE(fTree, iPart), tof, decay_prob);
    }
  }

  return kTRUE;
}
