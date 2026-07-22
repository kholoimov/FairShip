// SPDX-License-Identifier: LGPL-3.0-or-later
// SPDX-FileCopyrightText: Copyright CERN for the benefit of the SHiP
// Collaboration

#include <filesystem>
#include <iostream>
#include <string>
#include <vector>

#include "EvtCalcGenerator.h"
#include "TFile.h"
#include "TTree.h"

namespace {
std::filesystem::path CreateVectorSchemaFile() {
  const auto path =
      std::filesystem::temp_directory_path() / "evtcalc_vector_schema.root";
  TFile output(path.c_str(), "RECREATE");
  TTree tree("Events", "LLP Simulation Data");

  Float_t motherPx = 1.0;
  Float_t motherPy = 2.0;
  Float_t motherPz = 3.0;
  Float_t motherEnergy = 4.5;
  Float_t motherMass = 1.5;
  Int_t motherPdg = 9900015;
  Float_t weight = 0.25;
  Float_t vertexX = 0.01;
  Float_t vertexY = -0.02;
  Float_t vertexZ = 12.0;
  std::vector<float> daughterPx = {0.1F, -0.1F};
  std::vector<float> daughterPy = {0.2F, -0.2F};
  std::vector<float> daughterPz = {0.3F, 0.4F};
  std::vector<float> daughterEnergy = {0.5F, 0.6F};
  std::vector<float> daughterMass = {0.0F, 0.0F};
  std::vector<int> daughterPdg = {11, -11};

  tree.Branch("LLP_px", &motherPx, "LLP_px/F");
  tree.Branch("LLP_py", &motherPy, "LLP_py/F");
  tree.Branch("LLP_pz", &motherPz, "LLP_pz/F");
  tree.Branch("LLP_E", &motherEnergy, "LLP_E/F");
  tree.Branch("LLP_m", &motherMass, "LLP_m/F");
  tree.Branch("LLP_pdg", &motherPdg, "LLP_pdg/I");
  tree.Branch("LLP_weight", &weight, "LLP_weight/F");
  tree.Branch("vtx_x", &vertexX, "vtx_x/F");
  tree.Branch("vtx_y", &vertexY, "vtx_y/F");
  tree.Branch("vtx_z", &vertexZ, "vtx_z/F");
  tree.Branch("d_px", &daughterPx);
  tree.Branch("d_py", &daughterPy);
  tree.Branch("d_pz", &daughterPz);
  tree.Branch("d_E", &daughterEnergy);
  tree.Branch("d_m", &daughterMass);
  tree.Branch("d_pdg", &daughterPdg);
  tree.Fill();
  tree.Write();
  output.Close();
  return path;
}
}  // namespace

int main(int argc, char** argv) {
  const bool useExternalInput = argc > 1;
  const auto inputPath = useExternalInput ? std::filesystem::path(argv[1])
                                          : CreateVectorSchemaFile();
  EvtCalcGenerator generator;
  if (!generator.Init(inputPath.c_str()) || generator.GetNevents() <= 0) {
    std::cerr << "Failed to initialize convert.C Events schema" << std::endl;
    return 1;
  }
  if (!useExternalInput) std::filesystem::remove(inputPath);
  std::cout << "EvtCalcGenerator convert.C schema test passed" << std::endl;
  return 0;
}
