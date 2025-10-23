#!/bin/bash

# Start and run the medical OCR pipeline notebooks step by step
# This script opens each notebook in sequence with proper dependencies

set -e

echo "Medical OCR Pipeline - Notebook Runner"
echo "======================================"

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if Jupyter is available
if ! command -v jupyter &> /dev/null; then
    echo -e "${YELLOW}WARNING: Jupyter not found. Installing...${NC}"
    pip install jupyter notebook ipykernel
fi

# Pipeline notebooks in execution order
NOTEBOOKS=(
    "01_blocks_all_mcp_compare.ipynb:Extract text blocks from all OCR engines"
    "02_cleanup_blocks.ipynb:Clean and normalize extracted blocks"
    "03_llm_cleanup.ipynb:Enhance text quality using LLM"
    "04_json_extraction.ipynb:Extract structured data to JSON"
    "05_merge_and_validate.ipynb:Merge and validate final output"
)

# Optional comparison and QA notebooks
QA_NOTEBOOKS=(
    "01a_check_page_quality.ipynb:Check page quality metrics"
    "01b_normalize_layout.ipynb:Normalize layout detection"
    "02a_segment_general.ipynb:General text segmentation"
    "03a_llm_cleanup_qa.ipynb:LLM cleanup quality assurance"
    "03b_chunkr_enhance.ipynb:Chunkr enhancement analysis"
    "04a_extraction_hardening.ipynb:Extraction robustness testing"
    "04b_extraction_QA.ipynb:Extraction quality assurance"
)

# Function to check if services are running
check_services() {
    echo -e "${BLUE}Checking service health...${NC}"
    
    if python scripts/health_check.py > /dev/null 2>&1; then
        echo -e "${GREEN}All services are healthy${NC}"
        return 0
    else
        echo -e "${RED}ERROR: Some services are not healthy${NC}"
        echo "Please start services first: ./scripts/start_all_services.sh"
        return 1
    fi
}

# Function to open notebook in new window
open_notebook() {
    local notebook_file="$1"
    local description="$2"
    local notebook_path="notebooks/$notebook_file"
    
    if [ ! -f "$notebook_path" ]; then
        echo -e "${RED}ERROR: Notebook not found: $notebook_path${NC}"
        return 1
    fi
    
    echo -e "${BLUE}Opening: $notebook_file${NC}"
    echo -e "${YELLOW}   $description${NC}"
    
    # Open in new terminal window with Jupyter
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        osascript -e "tell application \"Terminal\" to do script \"cd '$PROJECT_ROOT' && jupyter notebook '$notebook_path'\""
    else
        # Linux with xterm
        xterm -T "Jupyter - $notebook_file" \
              -geometry 120x40+$((100 + RANDOM % 300))+$((100 + RANDOM % 200)) \
              -e "cd '$PROJECT_ROOT' && jupyter notebook '$notebook_path'; echo 'Notebook closed. Press Enter to exit.'; read" &
    fi
    
    sleep 3  # Give notebook time to start
}

# Function to run notebooks in sequence
run_sequential() {
    echo -e "${BLUE}🔄 Running notebooks sequentially...${NC}"
    
    for notebook_info in "${NOTEBOOKS[@]}"; do
        IFS=':' read -r notebook description <<< "$notebook_info"
        
        echo ""
        echo -e "${YELLOW}📋 Next: $notebook${NC}"
        echo -e "   $description"
        echo ""
        read -p "Press Enter to open this notebook (or 'q' to quit): " input
        
        if [[ "$input" == "q" || "$input" == "quit" ]]; then
            echo "Exiting pipeline..."
            break
        fi
        
        open_notebook "$notebook" "$description"
        
        echo ""
        read -p "Complete this step and press Enter to continue (or 'q' to quit): " input
        
        if [[ "$input" == "q" || "$input" == "quit" ]]; then
            echo "Exiting pipeline..."
            break
        fi
    done
}

# Function to run notebooks in parallel
run_parallel() {
    echo -e "${BLUE}🚀 Opening all notebooks in parallel...${NC}"
    
    for notebook_info in "${NOTEBOOKS[@]}"; do
        IFS=':' read -r notebook description <<< "$notebook_info"
        open_notebook "$notebook" "$description"
    done
    
    echo -e "${GREEN}✅ All main notebooks opened${NC}"
    
    echo ""
    read -p "Open QA/analysis notebooks too? (y/N): " open_qa
    
    if [[ "$open_qa" == "y" || "$open_qa" == "Y" ]]; then
        echo -e "${BLUE}📊 Opening QA notebooks...${NC}"
        
        for notebook_info in "${QA_NOTEBOOKS[@]}"; do
            IFS=':' read -r notebook description <<< "$notebook_info"
            if [ -f "notebooks/$notebook" ]; then
                open_notebook "$notebook" "$description"
            else
                echo -e "${YELLOW}⚠️ Optional notebook not found: $notebook${NC}"
            fi
        done
    fi
}

# Function to show notebook overview
show_overview() {
    echo -e "${BLUE}📋 Pipeline Overview${NC}"
    echo "===================="
    echo ""
    echo -e "${YELLOW}Main Pipeline Notebooks:${NC}"
    for i, notebook_info in "${NOTEBOOKS[@]}"; do
        IFS=':' read -r notebook description <<< "$notebook_info"
        echo "  $((i+1)). $notebook"
        echo "     $description"
        echo ""
    done
    
    echo -e "${YELLOW}Optional QA/Analysis Notebooks:${NC}"
    for notebook_info in "${QA_NOTEBOOKS[@]}"; do
        IFS=':' read -r notebook description <<< "$notebook_info"
        if [ -f "notebooks/$notebook" ]; then
            echo "  • $notebook"
            echo "    $description"
        fi
    done
}

# Main execution
echo ""
echo "Choose execution mode:"
echo "1) Sequential - Open notebooks one by one with guidance"
echo "2) Parallel - Open all notebooks at once"
echo "3) Overview - Show notebook descriptions only"
echo "4) Health check only"

read -p "Enter choice (1-4): " mode

case $mode in
    1)
        if check_services; then
            run_sequential
        fi
        ;;
        
    2)
        if check_services; then
            run_parallel
        fi
        ;;
        
    3)
        show_overview
        ;;
        
    4)
        check_services
        python scripts/health_check.py
        ;;
        
    *)
        echo "Invalid choice. Showing overview..."
        show_overview
        ;;
esac

echo ""
echo -e "${BLUE}📖 Notebook Pipeline Information${NC}"
echo "=================================="
echo ""
echo -e "${YELLOW}Execution Order:${NC}"
echo "1. Extract blocks with all OCR engines"
echo "2. Clean and normalize text blocks"  
echo "3. Enhance with LLM processing"
echo "4. Extract structured JSON data"
echo "5. Validate and merge final output"
echo ""
echo -e "${YELLOW}Input/Output:${NC}"
echo "• Input: PDF files in input_pdfs/"
echo "• Output: Processed results in outputs/"
echo "• Logs: Service logs in xterm windows"
echo ""
echo -e "${YELLOW}Useful Tips:${NC}"
echo "• Run notebooks in order for best results"
echo "• Check service health if notebooks fail"
echo "• Monitor xterm windows for service logs"
echo "• Stop services: docker-compose down"