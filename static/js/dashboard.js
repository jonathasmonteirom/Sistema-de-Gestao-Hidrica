function mostrarToast(mensagem) {
    const toast = document.getElementById('toast');
    toast.textContent = mensagem;
    toast.style.display = 'block';
    setTimeout(() => {
        toast.style.display = 'none';
    }, 3500);
}

function corBarra(percentual) {
    if (percentual <= 20) return 'var(--danger)';
    if (percentual <= 45) return 'var(--warning)';
    return 'var(--primary)';
}

async function buscarPrevisao(id) {
    try {
        const resp = await fetch(`/api/reservatorios/${id}/previsao`);
        const dados = await resp.json();
        if (!resp.ok) return 'Aguardando mais leituras para calcular reta.';
        if (dados.mensagem) return dados.mensagem;
        return `Taxa: ${dados.taxa_descida_litros_por_segundo.toFixed(2)} L/s | Esgotamento: ${dados.previsao_fim_da_agua}`;
    } catch {
        return 'Previsão indisponível';
    }
}

async function carregarReservatorios() {
    try {
        const resp = await fetch('/api/reservatorios');
        const reservatorios = await resp.json();
        const container = document.getElementById('lista-reservatorios');

        if (reservatorios.length === 0) {
            container.innerHTML = '<div class="card">Nenhum reservatório cadastrado ainda.</div>';
            return;
        }

        const cardsHtml = await Promise.all(reservatorios.map(async (r) => {
            const volume = r.volume_atual_litros !== null ? r.volume_atual_litros : 0;
            const pct = Math.min(100, Math.max(0, (volume / r.capacidade_maxima_litros) * 100));
            const previsaoTexto = await buscarPrevisao(r.id);

            return `
                <div class="card">
                    <div class="card-header">
                        <h3>${r.nome}</h3>
                        <span class="ip-tag">${r.ip_sensor}</span>
                    </div>
                    <div class="tags">
                        <span class="tag">${r.familias_atendidas} famílias</span>
                        ${r.tem_servico_essencial
                            ? '<span class="tag essencial">Serviço Essencial</span>'
                            : '<span class="tag">Uso Residencial</span>'}
                    </div>
                    <div class="progress-wrapper">
                        <div class="progress-info">
                            <span>${volume.toFixed(2)} L / ${r.capacidade_maxima_litros} L</span>
                            <span>${pct.toFixed(0)}%</span>
                        </div>
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: ${pct}%; background-color: ${corBarra(pct)};"></div>
                        </div>
                    </div>
                    <div class="previsao-box">${previsaoTexto}</div>
                </div>
            `;
        }));

        container.innerHTML = cardsHtml.join('');
    } catch (erro) {
        console.error('Erro ao carregar reservatórios:', erro);
    }
}

async function carregarFila() {
    const criterio = document.getElementById('criterio-strategy').value;
    try {
        const resp = await fetch(`/api/atendimentos?criterio=${criterio}`);
        const dados = await resp.json();
        const tbody = document.getElementById('tabela-fila');

        if (!dados.fila_prioridade || dados.fila_prioridade.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="7" class="empty-state">
                        Nenhum chamado pendente no momento. Será aberto alertas automaticamente quando alguma cisterna entrar em nível crítico.
                    </td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = dados.fila_prioridade.map(item => `
            <tr>
                <td><span class="pos-badge">${item.posicao_fila}</span></td>
                <td><strong>${item.reservatorio}</strong><br><small class="sensor-ip">IP: ${item.ip_sensor}</small></td>
                <td>${item.familias_atendidas} famílias</td>
                <td>${item.tem_servico_essencial ? 'Sim (Escola/Saúde)' : 'Não'}</td>
                <td>${item.dias_restantes_estimados !== null ? item.dias_restantes_estimados.toFixed(4) + ' dias' : '-'}</td>
                <td>${item.data_alerta}</td>
                <td>
                    <button class="btn-concluir" data-id="${item.id_atendimento}">
                        Concluir Entrega
                    </button>
                </td>
            </tr>
        `).join('');
    } catch (erro) {
        console.error('Erro ao carregar fila:', erro);
    }
}

async function concluirAtendimento(id) {
    try {
        const resp = await fetch(`/api/atendimentos/${id}/concluir`, {
            method: 'PATCH'
        });
        const dados = await resp.json();
        if (resp.ok) {
            mostrarToast(dados.mensagem);
            atualizarPainel();
        } else {
            mostrarToast(dados.erro || 'Erro ao concluir atendimento.');
        }
    } catch {
        mostrarToast('Falha de comunicação com o servidor.');
    }
}

function atualizarPainel() {
    carregarReservatorios();
    carregarFila();
}

document.addEventListener('DOMContentLoaded', () => {
    const seletorStrategy = document.getElementById('criterio-strategy');
    const tabelaFila = document.getElementById('tabela-fila');

    seletorStrategy.addEventListener('change', carregarFila);

    tabelaFila.addEventListener('click', (evento) => {
        const botao = evento.target.closest('.btn-concluir');
        if (botao) {
            const idAtendimento = botao.getAttribute('data-id');
            concluirAtendimento(idAtendimento);
        }
    });

    atualizarPainel();
    setInterval(atualizarPainel, 3000);
});