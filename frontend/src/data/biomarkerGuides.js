export const BIOMARKER_GUIDES = {
  EGFR: {
    role: 'Đánh giá tốc độ lọc chất thải và dịch dư thừa của hai quả thận qua cầu thận. Đây là chỉ số quan trọng nhất phản ánh chức năng thận còn lại.',
    lowMeaning:
      'Thận đang giảm khả năng lọc độc tố (như Ure, Creatinin) và điều hòa muối nước. Dưới 60 mL/min/1.73m2 kéo dài gợi ý bệnh thận mạn; từ 60–89 là giảm nhẹ cần theo dõi và bảo vệ thận.',
    highMeaning:
      'eGFR ≥ 90 mL/min/1.73m2 cho thấy chức năng lọc của cầu thận tốt. (Đôi khi tăng lọc quá mức gặp ở giai đoạn đầu tiểu đường, cần kiểm tra thêm đạm niệu).',
    eatToBalance: [
      'Đạm vừa đủ theo phác đồ (ưu tiên đạm quý dễ tiêu: cá nạc, lòng trắng trứng, ức gà, đậu phụ).',
      'Rau củ ít Kali nếu thận đã giảm nhiều (bầu, bí xanh, cải bắp, súp lơ).',
      'Chất béo tốt (dầu ô liu, dầu mè, cá hồi) giúp giảm áp lực mạch máu thận.',
    ],
    avoidToBalance: [
      'Ăn mặn: nước mắm mặn, dưa muối, mì gói, đồ hộp, xúc xích (làm tăng huyết áp hại cầu thận).',
      'Ăn quá nhiều đạm động vật (thịt đỏ, nội tạng) gây tăng tải lọc cho thận.',
      'Thuốc giảm đau NSAID (Ibuprofen, Diclofenac...) hoặc lá cây/thuốc nam không rõ nguồn gốc.',
    ],
    lifestyleNote: 'Kiểm soát huyết áp ổn định (< 130/80 mmHg), uống lượng nước vừa phải theo chỉ dẫn bác sĩ và tránh mất nước.',
  },
  CREATININE: {
    role: 'Sản phẩm thải tự nhiên từ chuyển hóa cơ bắp, được thận lọc và thải toàn bộ ra ngoài qua nước tiểu.',
    highMeaning:
      'Thận lọc chậm lại khiến Creatinin tích tụ trong máu, thường gặp khi chức năng thận suy giảm, mất nước nặng hoặc ăn quá nhiều thịt trước xét nghiệm.',
    lowMeaning:
      'Thường do khối lượng cơ ít (người gầy, người lớn tuổi) hoặc ăn thiếu đạm kéo dài; hiếm khi nguy hiểm trừ khi suy dinh dưỡng.',
    eatToBalance: [
      'Cân bằng lượng đạm hợp lý theo cân nặng và mức lọc cầu thận (không ăn dồn quá nhiều thịt trong 1 bữa).',
      'Tăng cường rau xanh, chất xơ hòa tan (yến mạch, táo, rau luộc) giúp hỗ trợ đào thải chất cặn.',
      'Chia nhỏ bữa ăn để giảm gánh nặng chuyển hóa cho thận.',
    ],
    avoidToBalance: [
      'Thịt đỏ quá nhiều (bò, trâu, nội tạng), thực phẩm bổ sung Creatine tập gym.',
      'Đồ ăn chế biến sẵn nhiều muối và phụ gia Phosphat.',
      'Rượu bia và nước ngọt có ga gây mất nước, tăng áp lực lọc cầu thận.',
    ],
    lifestyleNote: 'Uống đủ nước (nếu chưa có chỉ định hạn chế nước) và tránh vận động quá sức ngay trước ngày lấy máu xét nghiệm.',
  },
  UREA: {
    role: 'Sản phẩm thoái hóa cuối cùng của chất đạm (Protein) tại gan, sau đó được thận đào thải qua nước tiểu.',
    highMeaning:
      'Gặp khi thận giảm đào thải, chế độ ăn quá dư đạm, cơ thể bị mất nước hoặc nhiễm trùng/sốt cao làm tăng dị hóa đạm.',
    lowMeaning:
      'Có thể do ăn quá ít chất đạm (suy dinh dưỡng), ăn kiêng đạm quá mức hoặc suy giảm chức năng tổng hợp ở gan.',
    eatToBalance: [
      'Ăn đúng ngưỡng đạm trong thực đơn: đủ để không mất cơ nhưng không dư gây tăng Ure máu.',
      'Ưu tiên tinh bột hấp thu chậm (cơm gạo lứt, khoai, bún gạo) để cung cấp năng lượng thay thế, tránh cơ thể đốt đạm sinh năng lượng.',
      'Uống đủ nước rải đều trong ngày (theo mức nước tiểu nếu bị suy thận nặng).',
    ],
    avoidToBalance: [
      'Ăn quá nhiều thịt, hải sản, trứng, sữa giàu đạm cùng lúc.',
      'Thịt xông khói, giò chả, đồ kho mặn kéo dài.',
      'Nhịn ăn hoặc bỏ bữa khiến cơ thể tự tiêu cơ làm tăng Ure máu.',
    ],
    lifestyleNote: 'Nếu vừa bị suy thận vừa thiếu cân, cần cân chỉnh đúng tỷ lệ Calo/Đạm thay vì kiêng đạm cực đoan.',
  },
  GLUCOSE: {
    role: 'Nguồn đường chính trong máu cung cấp năng lượng tức thời cho não bộ, cơ bắp và toàn bộ tế bào cơ thể.',
    highMeaning:
      'Cơ thể thiếu Insulin hoặc đề kháng Insulin (tiểu đường/tiền tiểu đường). Đường huyết cao kéo dài làm tổn thương mạch máu nhỏ ở thận, mắt và thần kinh.',
    lowMeaning:
      'Hạ đường huyết (< 3.9 mmol/L) dễ gây run tay, vã mồ hôi, chóng mặt, thậm chí hôn mê nếu không bổ sung đường kịp thời.',
    eatToBalance: [
      'Nếu CAO: ưu tiên ngũ cốc nguyên hạt chỉ số đường huyết thấp (gạo lứt, yến mạch), ăn rau xanh trước khi ăn cơm để làm chậm hấp thu đường.',
      'Chia nhỏ 4–5 bữa vừa phải trong ngày, kết hợp đạm nạc + chất xơ.',
      'Nếu THẤP: uống ngay 1/2 ly nước đường/nước trái cây hoặc 2–3 viên kẹo ngọt, sau đó ăn nhẹ tinh bột.',
    ],
    avoidToBalance: [
      'Đường tinh luyện, bánh kẹo ngọt, trà sữa, nước ngọt, mật ong (khi đường huyết đang cao).',
      'Cơm trắng ăn nhiều một lúc, xôi nếp, bánh mì trắng, trái cây quá chín ngọt (sầu riêng, nhãn, vải, xoài chín).',
      'Bỏ bữa hoặc uống rượu khi đói (rất dễ gây tụt đường huyết nguy hiểm).',
    ],
    lifestyleNote: 'Đi bộ nhẹ 15–30 phút sau bữa ăn chính giúp cơ bắp tiêu thụ đường tự nhiên mà không gây tụt đường đột ngột.',
  },
  HBA1C: {
    role: 'Phản ánh mức đường huyết trung bình của cơ thể trong suốt 2–3 tháng gần nhất (độ chính xác ổn định hơn Glucose đo 1 thời điểm).',
    highMeaning:
      'Kiểm soát đường huyết trong 3 tháng qua chưa đạt mục tiêu (5.7–6.4%: tiền tiểu đường; ≥ 6.5%: ngưỡng chẩn đoán/kiểm soát kém), làm tăng nguy cơ biến chứng thận và tim mạch.',
    lowMeaning:
      'Dưới 4.0% rất hiếm, có thể gặp nếu thiếu máu hoặc tụt đường huyết lặp lại nhiều lần (người đang tiêm Insulin cần chú ý tránh hạ đường huyết ban đêm).',
    eatToBalance: [
      'Duy trì đều đặn tinh bột GI thấp (gạo lứt, miến dong, đậu đỗ) trong mỗi bữa.',
      'Bổ sung chất xơ từ rau lá, mướp đắng, đậu bắp, hạt chia giúp giảm đỉnh đường sau ăn.',
      'Ăn đủ đạm nạc để giữ khối cơ — cơ bắp khỏe giúp tiêu thụ đường hiệu quả hơn.',
    ],
    avoidToBalance: [
      'Thói quen ăn vặt đồ ngọt, nước ép đóng hộp, chè, kem.',
      'Ăn tối quá muộn nhiều tinh bột và chất béo bão hòa.',
      'Ăn uống thất thường lúc nhịn đói lúc ăn bù quá no.',
    ],
    lifestyleNote: 'Mục tiêu HbA1c thường < 7.0% với đa số người đái tháo đường (hoặc < 6.5% ở người trẻ mới mắc). Cần xét nghiệm lại mỗi 3 tháng.',
  },
  K: {
    role: 'Khoáng chất thiết yếu giúp dẫn truyền xung thần kinh, co bóp cơ và đặc biệt là giữ nhịp tim đập ổn định.',
    highMeaning:
      'NGUY HIỂM nếu tăng cao (> 5.5 mmol/L): Kali ứ lại do thận thải kém có thể gây yếu cơ, tê bì và rối loạn nhịp tim nặng, thậm chí ngừng tim.',
    lowMeaning:
      'Hạ Kali máu (< 3.5 mmol/L) gây mệt mỏi, chuột rút, yếu chi, táo bón và cũng gây loạn nhịp tim (hay gặp khi dùng thuốc lợi tiểu hoặc tiêu chảy).',
    eatToBalance: [
      'Nếu CAO: chọn rau củ ít Kali (bầu, bí đao, su su, cải bắp, dưa leo); thái nhỏ và ngâm/luộc bỏ nước đầu trước khi chế biến giúp giảm 30–50% Kali.',
      'Chọn trái cây ít Kali: táo, lê, dứa, dưa hấu (ăn lượng vừa phải).',
      'Nếu THẤP: bổ sung chuối, cam, khoai tây, rau ngót, bơ theo hướng dẫn bác sĩ.',
    ],
    avoidToBalance: [
      'Khi Kali CAO: tránh chuối tiêu, cam, bơ, sầu riêng, nước dừa, khoai tây, cà chua cô đặc, rau dền, nấm khô, nước hầm xương/nước luộc rau.',
      'Muối ăn kiêng có gốc Kali (KCl) thay thế muối thường.',
      'Nước ngọt màu sẫm, sô-cô-la, các loại hạt sấy khô ăn quá nhiều.',
    ],
    lifestyleNote: 'Không tự ý uống viên bổ sung Kali hay nước điện giải khi chưa kiểm tra Kali máu nếu bạn có bệnh thận.',
  },
  NA: {
    role: 'Giữ cân bằng lượng nước trong cơ thể, điều hòa huyết áp và hỗ trợ hoạt động thần kinh – cơ.',
    highMeaning:
      'Gặp khi mất nước nhiều (sốt, tiêu chảy, uống quá ít nước) hoặc ăn quá mặn kéo dài, gây khát dữ dội, phù, tăng huyết áp và lú lẫn.',
    lowMeaning:
      'Hạ Natri máu (< 135 mmol/L) thường do uống quá nhiều nước trong khi thận thải kém, suy tim nặng, hoặc tác dụng phụ thuốc lợi tiểu — gây buồn nôn, đau đầu, lơ mơ.',
    eatToBalance: [
      'Nêm nếm nhạt vừa đủ (khoảng 3–5g muối/ngày tùy phác đồ tăng huyết áp/suy tim/thận).',
      'Dùng gia vị tự nhiên tạo hương (hành, tỏi, gừng, chanh, tiêu, thì là) để món ăn ngon mà không cần nhiều muối.',
      'Nếu bị hạ Natri máu do uống thừa nước: điều chỉnh lượng nước uống theo đúng khuyến cáo của bác sĩ.',
    ],
    avoidToBalance: [
      'Mắm tôm, mắm ruốc, cá khô, mắm tép, dưa cà muối, mì ăn liền, snack mặn.',
      'Thịt chế biến sẵn: giò lụa, chả, lạp xưởng, xúc xích, đồ hộp.',
      'Bột canh, hạt nêm, xì dầu dùng quá tay khi nấu nướng.',
    ],
    lifestyleNote: 'Đọc bảng dinh dưỡng trên bao bì (1g muối ≈ 400mg Natri) để kiểm soát tổng Natri cả ngày.',
  },
  PHOSPHATE: {
    role: 'Kết hợp với Canxi tạo nên độ cứng chắc cho xương, răng và tham gia quá trình dự trữ năng lượng tế bào (ATP).',
    highMeaning:
      'Ở người suy thận, Phospho không thải được sẽ tích tụ trong máu, kéo Canxi ra khỏi xương làm loãng xương, ngứa da và vôi hóa mạch máu/van tim.',
    lowMeaning:
      'Ít gặp, có thể do suy dinh dưỡng nặng, kém hấp thu hoặc thiếu Vitamin D kéo dài, gây yếu cơ và đau xương.',
    eatToBalance: [
      'Ưu tiên nguồn đạm có tỷ lệ Phospho thấp hơn như lòng trắng trứng, thịt gà nạc, cá nạc tươi (thay vì thịt hộp/nội tạng).',
      'Chọn sữa chuyên biệt cho người bệnh thận (ít Phospho và Kali) nếu bác sĩ khuyên dùng.',
      'Bổ sung rau xanh tự nhiên (Phospho thực vật hấp thu ít hơn nhiều so với phụ gia công nghiệp).',
    ],
    avoidToBalance: [
      'Phụ gia Phosphat vô cơ trong đồ chế biến sẵn, xúc xích, thịt nguội, nước ngọt cola màu đen (cơ thể hấp thu gần 100%).',
      'Nội tạng động vật (gan, tim, bầu dục), trứng cá, tôm khô, phô mai cứng.',
      'Ăn quá nhiều hạt (hạt điều, hạnh nhân, vừng, đậu phộng) nếu Phospho máu đang vượt ngưỡng.',
    ],
    lifestyleNote: 'Nếu bác sĩ kê thuốc gắn Phosphat (uống ngay trong bữa ăn), cần uống đúng giờ để thuốc phát huy tác dụng.',
  },
  ALBUMIN: {
    role: 'Loại Protein quan trọng nhất do gan sản xuất, giúp giữ nước nằm lại trong lòng mạch (tránh phù nề) và vận chuyển dưỡng chất, thuốc men.',
    lowMeaning:
      'Thấp (< 35 g/L) làm dịch thoát ra ngoài mạch máu gây phù chân, tràn dịch, suy giảm miễn dịch và chậm lành vết thương. Thường do mất đạm qua nước tiểu (hội chứng thận hư), suy dinh dưỡng hoặc bệnh gan.',
    highMeaning:
      'Thường chỉ phản ánh tình trạng cô đặc máu nhẹ do thiếu nước tạm thời, hiếm khi là bệnh lý.',
    eatToBalance: [
      'Bổ sung đủ đạm chất lượng cao (lòng trắng trứng, thịt nạc, cá, ức gà, đậu phụ, sữa phù hợp bệnh lý).',
      'Ăn đủ Calo từ tinh bột và chất béo tốt để cơ thể không "đốt" mất đạm dự trữ.',
      'Chia nhiều bữa nhỏ nếu ăn uống kém ngon miệng.',
    ],
    avoidToBalance: [
      'Ăn kiêng đạm quá mức một cách tự phát (dễ làm Albumin tụt sâu thêm).',
      'Ăn quá mặn (làm tình trạng phù nề nặng hơn khi Albumin thấp).',
      'Rượu bia và thức ăn ôi thiu làm tổn thương gan.',
    ],
    lifestyleNote: 'Người có Albumin thấp kèm đạm niệu cao cần tuân thủ chính xác mức đạm bác sĩ tính theo cân nặng.',
  },
  URINE_PROTEIN: {
    role: 'Bình thường màng lọc cầu thận giữ lại gần như toàn bộ Protein trong máu; nước tiểu hầu như không có đạm.',
    highMeaning:
      'Dấu hiệu màng lọc cầu thận đang bị tổn thương, để rò rỉ đạm ra nước tiểu (nước tiểu thường có nhiều bọt lâu tan). Cần can thiệp sớm để làm chậm suy thận.',
    lowMeaning:
      '≤ 0.15 g/24h là mức bình thường tốt, chứng tỏ màng lọc cầu thận vẫn kín và khỏe mạnh.',
    eatToBalance: [
      'Ăn lượng đạm vừa đủ theo phác đồ bệnh thận/tiểu đường (không dư thừa gây tăng áp lực cầu thận).',
      'Tăng rau xanh giàu chất chống oxy hóa và chất béo không bão hòa (cá béo, dầu thực vật).',
      'Ăn nhạt để giảm áp lực lọc qua màng cầu thận.',
    ],
    avoidToBalance: [
      'Bữa ăn quá nhiều thịt đỏ, hải sản, đạm động vật.',
      'Thức ăn mặn, nước chấm đậm, đồ ăn nhanh.',
      'Đường huyết và huyết áp tăng cao không kiểm soát.',
    ],
    lifestyleNote: 'Kiểm soát tốt huyết áp và đường huyết là cách hiệu quả nhất giúp giảm lượng đạm rò rỉ qua nước tiểu.',
  },
  CHOLESTEROL: {
    role: 'Thành phần tạo nên màng tế bào, hormone và vitamin D trong cơ thể, nhưng dư thừa sẽ lắng đọng vào thành mạch máu.',
    highMeaning:
      'Làm tăng nguy cơ xơ vữa động mạch, hẹp lòng mạch và tai biến mạch máu não / nhồi máu cơ tim (đặc biệt nguy hiểm khi đi kèm tiểu đường hoặc suy thận).',
    lowMeaning:
      'Thường nằm trong ngưỡng tốt; nếu quá thấp (< 3.0 mmol/L) mới cần xem xét suy dinh dưỡng hoặc cường giáp.',
    eatToBalance: [
      'Chất xơ hòa tan (yến mạch, đậu đỗ, rau xanh, táo, ổi) giúp "quét" Cholesterol thừa qua đường tiêu hóa.',
      'Dùng dầu thực vật (ô liu, hướng dương, đậu nành), ăn cá 2–3 bữa/tuần.',
      'Chọn thịt nạc bỏ da, luộc/hấp thay vì chiên rán ngập dầu.',
    ],
    avoidToBalance: [
      'Nội tạng động vật (óc, gan, lòng, cật), da gà/vịt, mỡ heo, thịt ba chỉ.',
      'Đồ chiên rán nhiều dầu dùng lại, bánh ngọt công nghiệp chứa chất béo chuyển hóa (Trans fat).',
      'Ăn quá nhiều lòng đỏ trứng gà (> 3 quả/tuần khi mỡ máu đang cao).',
    ],
    lifestyleNote: 'Tập thể dục đều đặn tối thiểu 30 phút/ngày giúp cơ thể chuyển hóa và hạ mỡ máu tự nhiên.',
  },
  TRIGLYCERIDE: {
    role: 'Dạng chất béo dự trữ năng lượng chính của cơ thể, tăng nhanh sau bữa ăn nhiều tinh bột, đường hoặc rượu bia.',
    highMeaning:
      'Triglycerid cao (> 1.7 mmol/L) thúc đẩy gan nhiễm mỡ và xơ vữa mạch; nếu tăng rất cao (> 5.6 mmol/L) có nguy cơ gây viêm tụy cấp.',
    lowMeaning:
      'Mức bình thường thấp thường có lợi cho tim mạch; chỉ cần chú ý ăn đủ Calo nếu bị suy kiệt.',
    eatToBalance: [
      'Cá biển giàu Omega-3 (cá hồi, cá thu, cá trích — kiểm soát lượng vừa phải nếu có bệnh thận).',
      'Ngũ cốc nguyên hạt, rau xanh đậm, các loại đậu thay cho tinh bột tinh chế.',
      'Kiểm soát tổng lượng tinh bột và đường trong ngày.',
    ],
    avoidToBalance: [
      'Rượu bia (nguyên nhân làm Triglycerid tăng vọt nhanh nhất).',
      'Đồ ngọt, nước ngọt có ga, trà sữa, bánh kẹo, hoa quả quá ngọt.',
      'Cơm trắng ăn quá nhiều, đồ nếp, thịt mỡ và đồ chiên xào nhiều dầu.',
    ],
    lifestyleNote: 'Giảm 5–10% cân nặng (nếu thừa cân) và kiêng rượu bia thường giúp Triglycerid giảm rõ rệt chỉ sau 1–2 tháng.',
  },
  LDL: {
    role: 'Thường gọi là "Cholesterol xấu" — vận chuyển Cholesterol từ gan đi vào máu và dễ bám dính tạo mảng xơ vữa trên thành động mạch.',
    highMeaning:
      'LDL cao là yếu tố nguy cơ trực tiếp gây tắc nghẽn mạch vành (nhồi máu cơ tim), đột quỵ và làm hẹp mạch máu nuôi thận.',
    lowMeaning:
      'LDL càng thấp trong ngưỡng cho phép thì nguy cơ xơ vữa tim mạch càng thấp.',
    eatToBalance: [
      'Chất xơ hòa tan từ yến mạch, hạt lanh, đậu nành, rau đay, mồng tơi, táo.',
      'Chất béo đơn không bão hòa: dầu ô liu, quả bơ (lượng vừa nếu thận không hạn chế Kali), hạnh nhân.',
      'Đạm thực vật (đậu phụ, sữa đậu nành ít đường) thay thế một phần thịt đỏ.',
    ],
    avoidToBalance: [
      'Chất béo bão hòa: mỡ động vật, bơ sữa nguyên kem, phô mai, thịt bò mỡ, xúc xích.',
      'Bánh quy, snack, gà rán, khoai tây chiên chứa chất béo bão hòa và Trans fat.',
      'Nước cốt dừa, dầu cọ dùng thường xuyên.',
    ],
    lifestyleNote: 'Người có bệnh tiểu đường hoặc bệnh thận thường được bác sĩ đặt mục tiêu LDL chặt chẽ hơn nữa (< 2.6 hoặc < 1.8 mmol/L).',
  },
  HDL: {
    role: 'Thường gọi là "Cholesterol tốt" — đóng vai trò như xe dọn rác thu gom Cholesterol dư thừa từ thành mạch máu đưa về gan xử lý.',
    lowMeaning:
      'HDL thấp (< 1.0 mmol/L) làm giảm khả năng tự bảo vệ lòng mạch trước mảng xơ vữa, tăng nguy cơ tim mạch.',
    highMeaning:
      'HDL cao (≥ 1.0 mmol/L) là tín hiệu bảo vệ tim mạch rất tốt.',
    eatToBalance: [
      'Chất béo lành mạnh: dầu ô liu, dầu cải, cá hồi, cá ngừ, hạt óc chó (lượng vừa phải).',
      'Rau củ quả tươi giàu chất chống oxy hóa (bông cải xanh, ớt chuông, quả mọng).',
      'Ngũ cốc nguyên cám và các loại đậu.',
    ],
    avoidToBalance: [
      'Thuốc lá (hút thuốc làm tụt HDL rất mạnh).',
      'Đồ chiên công nghiệp, thực phẩm chứa Trans fat và đường tinh luyện.',
      'Lối sống ít vận động, ngồi lâu kéo dài.',
    ],
    lifestyleNote: 'Vận động hiếu khí đều đặn (đi bộ nhanh, đạp xe, bơi lội 150 phút/tuần) là cách hiệu quả nhất để nâng HDL tự nhiên.',
  },
  URIC_ACID: {
    role: 'Sản phẩm chuyển hóa cuối cùng của nhân Purin (từ tế bào cơ thể và thực phẩm giàu đạm), được thải chủ yếu qua thận.',
    highMeaning:
      'Acid uric tăng cao (> 420 µmol/L) dễ kết tinh thành tinh thể sắc nhọn tại khớp gây cơn Gout cấp (sưng đau ngón chân cái/khớp gối) và tạo sỏi urat làm hại thận.',
    lowMeaning:
      'Thường không đáng ngại; chỉ cần đảm bảo ăn uống đủ đạm để không bị thiếu chất.',
    eatToBalance: [
      'Uống đủ nước mỗi ngày (1.5–2 lít nếu thận chưa phải hạn chế nước) để thận hòa loãng và thải Acid uric.',
      'Thực phẩm ít Purin & giúp thải urat: rau xanh, quả anh đào, dâu, cam/ổi giàu Vitamin C vừa phải, sữa ít béo, trứng.',
      'Cà phê đen không đường hoặc trà nhạt (lượng vừa) hỗ trợ giảm nhẹ Acid uric.',
    ],
    avoidToBalance: [
      'Thực phẩm cực giàu Purin: nội tạng (gan, tim, lòng), thịt đỏ (bò, dê), hải sản (tôm, cua, sò, cá trích, cá mòi, cá cơm).',
      'Rượu bia (đặc biệt là bia — vừa chứa nhân Purin vừa khóa đường thải Acid uric ở thận).',
      'Nước ngọt chứa si-rô đường Fructose và nước hầm xương ninh kỹ.',
    ],
    lifestyleNote: 'Không nhịn ăn đột ngột hoặc giảm cân quá nhanh vì phân giải mô cơ sẽ làm Acid uric tăng vọt kích hoạt cơn đau Gout.',
  },
};
