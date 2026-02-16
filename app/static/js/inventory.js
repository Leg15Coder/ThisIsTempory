document.addEventListener('DOMContentLoaded', () => {
    const list = document.getElementById('inventoryList');
    const empty = document.getElementById('inventoryEmpty');

    async function loadInventory() {
        const res = await fetch('/api/inventory');
        const items = await res.json();
        renderItems(items);
    }

    function rarityClass(rarity) {
        if (!rarity) return 'rarity-common';
        const map = {
            'Обычный': 'rarity-common',
            'Необычный': 'rarity-uncommon',
            'Редкий': 'rarity-rare',
            'Эпический': 'rarity-epic',
            'Легендарный': 'rarity-legendary'
        };
        return map[rarity] || 'rarity-common';
    }

    function renderItems(items) {
        list.innerHTML = '';
        if (!items || items.length === 0) {
            empty.style.display = 'block';
            return;
        }
        empty.style.display = 'none';

        items.forEach(item => {
            const card = document.createElement('div');
            card.className = `shop-item-card ${rarityClass(item.shop_item?.rarity)}`;
            card.innerHTML = `
                <div class="item-visual">
                    <div>${item.shop_item?.icon || '🎒'}</div>
                    <div class="item-rarity-badge">${item.shop_item?.rarity || ''}</div>
                </div>
                <div class="item-details">
                    <div class="item-name">${item.shop_item?.name || 'Предмет'}</div>
                    <div class="item-description">${item.shop_item?.description || ''}</div>
                    <div class="item-footer">
                        <div class="item-qty">Доступно: ${item.available_quantity}</div>
                        <button class="btn-use" data-id="${item.id}">Использовать</button>
                    </div>
                </div>
            `;
            const useBtn = card.querySelector('.btn-use');
            useBtn.addEventListener('click', async () => {
                const resp = await fetch('/api/inventory/use', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ inventory_id: item.id, quantity: 1 })
                });
                if (!resp.ok) {
                    const err = await resp.json();
                    alert(err.detail || 'Ошибка использования');
                    return;
                }
                await loadInventory();
            });
            list.appendChild(card);
        });
    }

    loadInventory();
});

