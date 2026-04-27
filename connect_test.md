Agent 2 has provided the complete GCP setup guide. Here's what you need to do:                                                                                                                                     
                                                                        
  Quick Start - GCP Setup (30 min)                                                                                                                                                                                   
                                                                          
  # Step 1: Verify gcloud CLI is installed                                                                                                                                                                           
  gcloud version                                                                
                                                                                                                                                                                                                     
  # Step 2: Authenticate with GCP                                                      
  gcloud auth login                                                                                                                                                                                                  
                                                                                                                                                                                                                     
  # Step 3: Create GCP project                                                                                                                                                                                       
  gcloud projects create autotube-pipeline --name="AutoTube Pipeline"                                                                                                                                                
  gcloud config set project autotube-pipeline                           
                                                                                                                                                                                                                     
  # Step 4: Enable Compute Engine API           
  gcloud services enable compute.googleapis.com                                                                                                                                                                      
                                                                          
  # Step 5: Create e2-micro VM (always-free tier)                                      
  gcloud compute instances create autotube-vm \
    --zone=us-central1-a \                                                                                                                                                                                           
    --machine-type=e2-micro \                                                   
    --image-family=ubuntu-2204-lts \                                                                                                                                                                                 
    --image-project=ubuntu-os-cloud \                                                  
    --scopes=https://www.googleapis.com/auth/cloud-platform                     
                                                                                                                                                                                                                     
  # Step 6: SSH into VM                                                                
  gcloud compute ssh autotube-vm --zone=us-central1-a                                                                                                                                                                
                                                                                                                                                                                                                     
  # (On the VM, run these):                                               
  git clone https://github.com/harshdeepsingh/autotube.git                                                                                                                                                           
  cd autotube                                                           
  python3 -m venv .venv                                                                                                                                                                                              
  source .venv/bin/activate                                               
  pip install -r requirements.txt                                                                                                                                                                                    
  mkdir -p logs                                                         
                                                                                                                                                                                                                     
  # Step 7: Add cron jobs (IST → UTC conversion)                          
  crontab -e                                                                                                                                                                                                         
  # Paste these 4 lines:                                                
  # 09:00 IST = 03:30 UTC                                                                                                                                                                                            
  # 12:00 IST = 06:30 UTC                                                 
  # 15:00 IST = 09:30 UTC                                                                                                                                                                                            
  # 18:00 IST = 12:30 UTC                                                       
  30 3 * * * cd ~/autotube && .venv/bin/python3 orchestrator.py >> logs/pipeline.log 2>&1                                                                                                                            
  30 6 * * * cd ~/autotube && .venv/bin/python3 orchestrator.py >> logs/pipeline.log 2>&1
  30 9 * * * cd ~/autotube && .venv/bin/python3 orchestrator.py >> logs/pipeline.log 2>&1                                                                                                                            
  30 12 * * * cd ~/autotube && .venv/bin/python3 orchestrator.py >> logs/pipeline.log 2>&1                                                                                                                           
                                                                                
  # Step 8: Test (still on VM)                                                                                                                                                                                       
  python3 orchestrator.py --dry-run --topic "Test Topic"                               
                                                                                                                                                                                                                     
  # Step 9: Exit VM                                                                                                                                                                                                  
  exit                                           