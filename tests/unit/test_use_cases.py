from unittest.mock import AsyncMock

import pytest

from app.application.use_cases.generate_invoices import GenerateInvoiceBatchUseCase
from app.application.use_cases.process_payment import ProcessPaidInvoiceUseCase
from app.domain.entities.invoice import Invoice, InvoiceStatus
from app.domain.validators import validate_tax_id
from app.domain.value_objects.money import Money


class TestValidateTaxId:
    """Suíte de testes para validação de CPF/CNPJ."""

    def test_valid_cnpj(self) -> None:
        """Deve validar CNPJ com pontuação."""
        assert validate_tax_id("20.018.183/0001-80") is True

    def test_valid_cpf(self) -> None:
        """Deve validar CPF com pontuação."""
        assert validate_tax_id("529.982.247-25") is True

    def test_invalid_cpf_all_same_digits(self) -> None:
        """CPF com todos os dígitos iguais deve ser inválido."""
        assert validate_tax_id("000.000.000-00") is False
        assert validate_tax_id("111.111.111-11") is False

    def test_invalid_cnpj_all_same_digits(self) -> None:
        """CNPJ com todos os dígitos iguais deve ser inválido."""
        assert validate_tax_id("11.111.111/1111-11") is False

    def test_garbage_string_returns_false(self) -> None:
        """Strings aleatórias devem ser inválidas."""
        assert validate_tax_id("abc-not-a-tax-id") is False

    def test_empty_string_returns_false(self) -> None:
        """String vazia deve ser inválida."""
        assert validate_tax_id("") is False

    def test_wrong_length_returns_false(self) -> None:
        """IDs com tamanho incorreto devem ser inválidos."""
        assert validate_tax_id("123.456.789") is False


class TestGenerateInvoiceBatchUseCase:
    """Suíte de testes para geração automática de faturas."""

    def _make_billing_side_effect(self):
        """Simula o retorno do provedor atribuindo IDs externos."""

        def _assign_ids(invoices: list[Invoice]) -> list[Invoice]:
            for i, inv in enumerate(invoices):
                inv.external_id = f"stark_inv_{i}"
                inv.status = InvoiceStatus.PENDING
            return invoices

        return _assign_ids

    @pytest.mark.asyncio
    async def test_batch_size_always_in_range(self) -> None:
        """O lote gerado deve respeitar os limites de tamanho mínimo e máximo."""
        mock_repo = AsyncMock()
        mock_billing = AsyncMock()
        mock_billing.create_invoices.side_effect = self._make_billing_side_effect()
        use_case = GenerateInvoiceBatchUseCase(repo=mock_repo, billing=mock_billing)
        batch_min, batch_max = (8, 12)
        for _ in range(5):
            results, _ = await use_case.execute(min_size=batch_min, max_size=batch_max)
            assert batch_min <= len(results) <= batch_max

    @pytest.mark.asyncio
    async def test_billing_gateway_called_with_all_invoices(self) -> None:
        """Deve chamar o provedor com todas as faturas geradas no lote."""
        mock_repo = AsyncMock()
        mock_billing = AsyncMock()
        mock_billing.create_invoices.side_effect = self._make_billing_side_effect()
        use_case = GenerateInvoiceBatchUseCase(repo=mock_repo, billing=mock_billing)
        results, _ = await use_case.execute()
        mock_billing.create_invoices.assert_called_once()
        args, _ = mock_billing.create_invoices.call_args
        assert len(args[0]) == len(results)

    @pytest.mark.asyncio
    async def test_repo_save_invoices_called_correctly(self) -> None:
        """Deve salvar cada fatura criada no repositório local."""
        mock_repo = AsyncMock()
        mock_billing = AsyncMock()
        mock_billing.create_invoices.side_effect = self._make_billing_side_effect()
        use_case = GenerateInvoiceBatchUseCase(repo=mock_repo, billing=mock_billing)
        results, _ = await use_case.execute(count=2)
        assert mock_repo.save_invoice.call_count == 2

    @pytest.mark.asyncio
    async def test_each_invoice_has_unique_name(self) -> None:
        """Nomes gerados devem ser aleatórios para evitar colisões no Sandbox."""
        mock_repo = AsyncMock()
        mock_billing = AsyncMock()
        mock_billing.create_invoices.side_effect = self._make_billing_side_effect()
        use_case = GenerateInvoiceBatchUseCase(repo=mock_repo, billing=mock_billing)
        results, _ = await use_case.execute(min_size=2, max_size=5)
        names = [inv.name for inv in results]
        assert len(set(names)) > 1


class TestProcessPaidInvoiceUseCase:
    """Suíte de testes para orquestração de processamento de pagamentos."""

    def _make_use_case(
        self, inv_repo, trans_repo, web_repo, gate
    ) -> ProcessPaidInvoiceUseCase:
        """Instancia o caso de uso com mocks injetados."""
        return ProcessPaidInvoiceUseCase(inv_repo, trans_repo, web_repo, gate)

    def _make_invoice(
        self,
        amount: int = 1000,
        status: InvoiceStatus = InvoiceStatus.PENDING,
        id: str = "00000000-0000-0000-0000-000000000001",
    ) -> Invoice:
        """Cria uma entidade Invoice para uso nos testes."""
        return Invoice(
            id=id,
            external_id="ext_stark-001",
            amount=Money(amount),
            tax_id="529.982.247-25",
            name="Test User",
            status=status,
        )

    @pytest.mark.asyncio
    async def test_idempotent_same_event_id_returns_true_without_processing(
        self,
    ) -> None:
        """Eventos já processados devem ser ignorados silenciosamente (Idempotência)."""
        invoice_repo, transfer_repo, webhook_repo, gateway = (
            AsyncMock(),
            AsyncMock(),
            AsyncMock(),
            AsyncMock(),
        )
        webhook_repo.log_webhook_event.return_value = False
        use_case = self._make_use_case(
            invoice_repo, transfer_repo, webhook_repo, gateway
        )
        result, _ = await use_case.execute(
            "stark", "credited", "evt_1", "ext_001", 1000, 50
        )
        assert result is True
        invoice_repo.get_invoice_by_external_id.assert_not_called()

    @pytest.mark.asyncio
    async def test_idempotent_invoice_already_credited_skips_transfer(self) -> None:
        """Faturas já creditadas não devem disparar novo repasse financeiro."""
        invoice_repo, transfer_repo, webhook_repo, gateway = (
            AsyncMock(),
            AsyncMock(),
            AsyncMock(),
            AsyncMock(),
        )
        webhook_repo.log_webhook_event.return_value = True
        invoice_repo.get_invoice_by_external_id.return_value = self._make_invoice(
            status=InvoiceStatus.CREDITED
        )
        use_case = self._make_use_case(
            invoice_repo, transfer_repo, webhook_repo, gateway
        )
        result, _ = await use_case.execute(
            "stark", "credited", "evt_1", "ext_001", 1000, 50
        )
        assert result is True
        gateway.execute_transfer.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_false_for_unknown_invoice(self) -> None:
        """Se a fatura não existe localmente, deve retornar False para sinalizar erro de rastreio."""
        invoice_repo, transfer_repo, webhook_repo, gateway = (
            AsyncMock(),
            AsyncMock(),
            AsyncMock(),
            AsyncMock(),
        )
        webhook_repo.log_webhook_event.return_value = True
        invoice_repo.get_invoice_by_external_id.return_value = None
        use_case = self._make_use_case(
            invoice_repo, transfer_repo, webhook_repo, gateway
        )
        result, _ = await use_case.execute(
            "stark", "credited", "evt_1", "unknown", 500, 0
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_transfer_amount_equals_liquid_amount_from_webhook(self) -> None:
        """O valor do repasse deve ser exatamente o valor bruto menos a taxa retida."""
        invoice_repo, transfer_repo, webhook_repo, gateway = (
            AsyncMock(),
            AsyncMock(),
            AsyncMock(),
            AsyncMock(),
        )
        webhook_repo.log_webhook_event.return_value = True
        invoice = self._make_invoice(amount=2000)
        invoice_repo.get_invoice_by_external_id.return_value = invoice
        transfer_repo.get_transfer_by_invoice_id.return_value = None
        use_case = self._make_use_case(
            invoice_repo, transfer_repo, webhook_repo, gateway
        )
        await use_case.execute("stark", "credited", "evt_1", "ext_001", 2000, 50)

        first_save_args = transfer_repo.save_transfer.call_args_list[0][0]
        transfer_intent = first_save_args[0]
        assert transfer_intent.fee.amount == 50
        assert transfer_intent.amount.amount == 1950

    @pytest.mark.asyncio
    async def test_marks_invoice_credited_after_successful_transfer(self) -> None:
        """Fatura deve ser marcada como creditada após o sucesso da transferência."""
        invoice_repo, transfer_repo, webhook_repo, gateway = (
            AsyncMock(),
            AsyncMock(),
            AsyncMock(),
            AsyncMock(),
        )
        webhook_repo.log_webhook_event.return_value = True
        invoice = self._make_invoice()
        invoice_repo.get_invoice_by_external_id.return_value = invoice
        transfer_repo.get_transfer_by_invoice_id.return_value = None
        use_case = self._make_use_case(
            invoice_repo, transfer_repo, webhook_repo, gateway
        )
        await use_case.execute("stark", "credited", "evt_1", "ext_001", 1000, 50)
        assert invoice.status == InvoiceStatus.CREDITED

    @pytest.mark.asyncio
    async def test_logs_webhook_event_correctly(self) -> None:
        """Deve registrar o evento no repositório para auditoria e deduplicação."""
        invoice_repo, transfer_repo, webhook_repo, gateway = (
            AsyncMock(),
            AsyncMock(),
            AsyncMock(),
            AsyncMock(),
        )
        webhook_repo.log_webhook_event.return_value = True
        invoice_repo.get_invoice_by_external_id.return_value = self._make_invoice()
        transfer_repo.get_transfer_by_invoice_id.return_value = None
        use_case = self._make_use_case(
            invoice_repo, transfer_repo, webhook_repo, gateway
        )
        raw_payload = {"event": "credited"}
        await use_case.execute(
            "starkbank",
            "credited",
            "evt_xyz",
            "ext_001",
            1000,
            50,
            raw_payload=raw_payload,
        )
        webhook_repo.log_webhook_event.assert_called_once_with(
            "starkbank", "credited", "evt_xyz", raw_payload
        )

    @pytest.mark.asyncio
    async def test_persists_transfer_intent_before_gateway_call(self) -> None:
        """O registro de intenção de transferência deve ser salvo antes da chamada externa (Prevenção de Data Loss)."""
        call_order = []
        invoice_repo, transfer_repo, webhook_repo, gateway = (
            AsyncMock(),
            AsyncMock(),
            AsyncMock(),
            AsyncMock(),
        )
        webhook_repo.log_webhook_event.return_value = True
        invoice_repo.get_invoice_by_external_id.return_value = self._make_invoice()
        transfer_repo.get_transfer_by_invoice_id.return_value = None

        async def record_save(t):
            call_order.append("db_save")

        async def record_gate(t):
            call_order.append("gate_call")
            return t

        transfer_repo.save_transfer.side_effect = record_save
        gateway.execute_transfer.side_effect = record_gate

        use_case = self._make_use_case(
            invoice_repo, transfer_repo, webhook_repo, gateway
        )
        await use_case.execute("stark", "credited", "evt_1", "ext_001", 1000, 50)
        assert call_order[0] == "db_save"
        assert call_order[1] == "gate_call"

    @pytest.mark.asyncio
    async def test_skips_transfer_when_liquid_amount_is_zero(self) -> None:
        """Se o valor líquido for zero após taxas, o repasse deve ser ignorado."""
        invoice_repo, transfer_repo, webhook_repo, gateway = (
            AsyncMock(),
            AsyncMock(),
            AsyncMock(),
            AsyncMock(),
        )
        webhook_repo.log_webhook_event.return_value = True
        invoice = self._make_invoice(amount=50)
        invoice_repo.get_invoice_by_external_id.return_value = invoice
        use_case = self._make_use_case(
            invoice_repo, transfer_repo, webhook_repo, gateway
        )
        result, _ = await use_case.execute(
            "stark", "credited", "evt_1", "ext_001", 50, 50
        )
        assert result is True
        gateway.execute_transfer.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_handles_prefixed_id_successfully(self) -> None:
        """Deve ser capaz de localizar a fatura via UUID interno como fallback se o ID externo falhar."""
        invoice_repo, transfer_repo, webhook_repo, gateway = (
            AsyncMock(),
            AsyncMock(),
            AsyncMock(),
            AsyncMock(),
        )
        expected_uuid = "019d604d-ba85-756c-87d9-3191fc6d5a5b"
        invoice = self._make_invoice(id=expected_uuid)
        invoice_repo.get_invoice_by_external_id.return_value = None
        invoice_repo.get_invoice_by_id.return_value = invoice
        webhook_repo.log_webhook_event.return_value = True
        use_case = self._make_use_case(
            invoice_repo, transfer_repo, webhook_repo, gateway
        )
        success, _ = await use_case.execute(
            "stark",
            "paid",
            "evt_1",
            "stark_1",
            1000,
            0,
            f"internal_id:inv_{expected_uuid}",
        )
        assert success is True
        invoice_repo.get_invoice_by_id.assert_called_once_with(expected_uuid)
