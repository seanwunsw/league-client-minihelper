/**
 * Searchable Combobox Component
 * Vanilla JS implementation with keyboard navigation
 */

class Combobox {
    constructor(container, options = {}) {
        this.container = container;
        this.options = options.options || [];
        this.value = options.value || null;
        this.placeholder = options.placeholder || 'Select...';
        this.onChange = options.onChange || (() => {});
        
        this.isOpen = false;
        this.selectedIndex = -1;
        this.filteredOptions = [];
        
        this.render();
        this.attachEvents();
    }
    
    render() {
        this.container.classList.add('combobox');
        
        // Input
        this.input = document.createElement('input');
        this.input.type = 'text';
        this.input.className = 'combobox-input';
        this.input.placeholder = this.placeholder;
        this.input.autocomplete = 'off';
        
        // Clear button
        this.clearBtn = document.createElement('span');
        this.clearBtn.className = 'combobox-clear';
        this.clearBtn.innerHTML = '×';
        this.clearBtn.title = 'Clear';
        
        // Dropdown
        this.dropdown = document.createElement('div');
        this.dropdown.className = 'combobox-dropdown';
        
        this.container.appendChild(this.input);
        this.container.appendChild(this.clearBtn);
        this.container.appendChild(this.dropdown);
        
        this.updateDisplay();
    }
    
    attachEvents() {
        // Input events
        this.input.addEventListener('focus', () => this.open());
        this.input.addEventListener('input', (e) => this.handleInput(e));
        this.input.addEventListener('keydown', (e) => this.handleKeydown(e));
        
        // Clear button
        this.clearBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            this.setValue(null);
        });
        
        // Click outside to close
        document.addEventListener('click', (e) => {
            if (!this.container.contains(e.target)) {
                this.close();
            }
        });
    }
    
    handleInput(e) {
        const query = e.target.value;
        this.filterOptions(query);
        this.open();
    }
    
    handleKeydown(e) {
        if (!this.isOpen) {
            if (e.key === 'ArrowDown' || e.key === 'Enter') {
                e.preventDefault();
                this.open();
            }
            return;
        }
        
        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                this.selectedIndex = Math.min(
                    this.selectedIndex + 1,
                    this.filteredOptions.length - 1
                );
                this.updateDropdown();
                this.scrollToSelected();
                break;
                
            case 'ArrowUp':
                e.preventDefault();
                this.selectedIndex = Math.max(this.selectedIndex - 1, 0);
                this.updateDropdown();
                this.scrollToSelected();
                break;
                
            case 'Enter':
                e.preventDefault();
                if (this.selectedIndex >= 0 && this.selectedIndex < this.filteredOptions.length) {
                    this.selectOption(this.filteredOptions[this.selectedIndex]);
                }
                break;
                
            case 'Escape':
                e.preventDefault();
                this.close();
                break;
        }
    }
    
    filterOptions(query) {
        const queryLower = query.toLowerCase();
        
        if (!query) {
            this.filteredOptions = [...this.options];
        } else {
            this.filteredOptions = this.options.filter(opt =>
                opt.label.toLowerCase().includes(queryLower)
            );
        }
        
        this.selectedIndex = this.filteredOptions.length > 0 ? 0 : -1;
        this.updateDropdown();
    }
    
    open() {
        this.isOpen = true;
        this.filterOptions(this.input.value);
        this.dropdown.classList.add('open');
    }
    
    close() {
        this.isOpen = false;
        this.dropdown.classList.remove('open');
        this.updateDisplay();
    }
    
    updateDropdown() {
        this.dropdown.innerHTML = '';
        
        // Add "None" option
        const noneOption = document.createElement('div');
        noneOption.className = 'combobox-option';
        noneOption.textContent = 'None';
        noneOption.dataset.value = '';
        noneOption.addEventListener('click', () => this.selectOption(null));
        this.dropdown.appendChild(noneOption);
        
        // Add filtered options
        this.filteredOptions.forEach((opt, index) => {
            const optionEl = document.createElement('div');
            optionEl.className = 'combobox-option';
            optionEl.textContent = opt.label;
            optionEl.dataset.value = opt.value;
            
            if (index === this.selectedIndex) {
                optionEl.classList.add('selected');
            }
            
            optionEl.addEventListener('click', () => this.selectOption(opt));
            this.dropdown.appendChild(optionEl);
        });
    }
    
    scrollToSelected() {
        if (this.selectedIndex < 0) return;
        
        // +1 because "None" is first
        const selectedEl = this.dropdown.children[this.selectedIndex + 1];
        if (selectedEl) {
            selectedEl.scrollIntoView({ block: 'nearest' });
        }
    }
    
    selectOption(option) {
        this.setValue(option ? option.value : null);
        this.close();
    }
    
    setValue(value) {
        const oldValue = this.value;
        this.value = value;
        
        if (value !== oldValue) {
            this.onChange(value);
        }
        
        this.updateDisplay();
        
        // Update has-value class
        if (value) {
            this.container.classList.add('has-value');
        } else {
            this.container.classList.remove('has-value');
        }
    }
    
    updateDisplay() {
        if (!this.value) {
            this.input.value = '';
            return;
        }
        
        const option = this.options.find(opt => opt.value === this.value);
        if (option) {
            this.input.value = option.label;
        } else {
            this.input.value = '';
        }
    }
    
    setOptions(options) {
        this.options = options;
        this.filterOptions(this.input.value);
        this.updateDisplay();
    }
    
    getValue() {
        return this.value;
    }
}

// Export for use in app.js
if (typeof module !== 'undefined' && module.exports) {
    module.exports = Combobox;
}
