// SPDX-License-Identifier: LGPL-3.0-or-later
// SPDX-FileCopyrightText: Copyright CERN for the benefit of the SHiP
// Collaboration

#ifndef SHIPGEN_EVTCALCGENERATOR_H_
#define SHIPGEN_EVTCALCGENERATOR_H_

#include <memory>
#include <vector>

#include "Generator.h"
#include "TFile.h"
#include "TTree.h"

class FairPrimaryGenerator;

class EvtCalcGenerator : public SHiP::Generator {
 public:
  /** default constructor **/
  EvtCalcGenerator();

  /** destructor **/
  ~EvtCalcGenerator() override;

  /** public method ReadEvent **/
  using SHiP::Generator::Init;
  Bool_t ReadEvent(FairPrimaryGenerator*) override;
  Bool_t Init(const char*, int) override;
  Bool_t Init(const char*) override;

  Int_t GetNevents() { return fNevents; }
  void SetPositions(Double_t zTa, Double_t zDV) {
    ztarget = zTa;       // units cm (midpoint)
    zDecayVolume = zDV;  // units cm (midpoint)
  }

 protected:
  Double_t ztarget, zDecayVolume;
  std::unique_ptr<TFile> fInputFile;
  std::unique_ptr<TTree> fTree;
  Bool_t BindBranches();
  Bool_t ValidateDaughters() const;
  Float_t fMotherPx = 0.;
  Float_t fMotherPy = 0.;
  Float_t fMotherPz = 0.;
  Float_t fMotherE = 0.;
  Float_t fMotherMass = 0.;
  Int_t fMotherPdg = 0;
  Float_t fDecayProbability = 0.;
  Float_t fVertexX = 0.;
  Float_t fVertexY = 0.;
  Float_t fVertexZ = 0.;
  std::vector<float>* fDaughterPx = nullptr;
  std::vector<float>* fDaughterPy = nullptr;
  std::vector<float>* fDaughterPz = nullptr;
  std::vector<float>* fDaughterE = nullptr;
  std::vector<float>* fDaughterMass = nullptr;
  std::vector<int>* fDaughterPdg = nullptr;

  int fNevents = 0;
  int fn = 0;
};

#endif  // SHIPGEN_EVTCALCGENERATOR_H_
