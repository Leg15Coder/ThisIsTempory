document.addEventListener('DOMContentLoaded', () => {
    const list = document.getElementById('shopList');
    const empty = document.getElementById('shopEmpty');

    async function loadItems() {
        const res = await fetch('/api/shop/items?available_only=false', { credentials: 'same-origin' });
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
            card.className = `shop-item-card ${rarityClass(item.rarity)}`;
            card.innerHTML = `
                <div class="item-visual">
                    <div>${item.icon || '🎁'}</div>
                    <div class="item-rarity-badge">${item.rarity}</div>
                </div>
                <div class="item-details">
                    <div class="item-name">${item.name}</div>
                    <div class="item-description">${item.description || ''}</div>
                    <div class="item-footer">
                        <div class="item-price">💰 ${item.price}</div>
                        <button class="btn-buy" ${item.is_available ? '' : 'disabled'} data-id="${item.id}">
                            Купить
                        </button>
                    </div>
                </div>
            `;
            const buyBtn = card.querySelector('.btn-buy');
            buyBtn.addEventListener('click', async () => {
                const qty = 1;
                const resp = await fetch('/api/inventory/purchase', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'same-origin',
                    body: JSON.stringify({ shop_item_id: item.id, quantity: qty })
                });
                if (!resp.ok) {
                    const err = await resp.json();
                    alert(err.detail || 'Ошибка покупки');
                    return;
                }
                await loadItems();
            });
            list.appendChild(card);
        });
    }

    // Делегированный обработчик submit: ловим submit событий на document
    async function handleCreateItemSubmit(form) {
        const data = Object.fromEntries(new FormData(form).entries());
        const payload = {
            name: data.name,
            price: Number(data.price || 0),
            description: data.description || null,
            rarity: data.rarity || 'common',
            icon: data.icon || null,
            stock: data.stock ? Number(data.stock) : null,
            is_available: data.is_available === 'on'
        };
        const resp = await fetch('/api/shop/items', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify(payload)
        });
        if (!resp.ok) {
            try {
                const err = await resp.json();
                alert(err.detail || 'Ошибка создания');
            } catch (e) {
                alert('Ошибка создания');
            }
            return;
        }
        // Сброс формы, закрытие модального оверлея если нужно
        try {
            form.reset();
            // Закрыть оверлей, если глобальная функция доступна
            if (window.closeShopModal) window.closeShopModal();
        } catch (e) {}
        await loadItems();
    }

    // Делегируем submit для форм, которые будут динамически добавлены (например, в оверлей)
    document.addEventListener('submit', function(e) {
        const target = e.target;
        if (!target) return;
        if (target.id === 'createItemForm') {
            e.preventDefault();
            handleCreateItemSubmit(target);
        }
    }, true);

    loadItems();
});
