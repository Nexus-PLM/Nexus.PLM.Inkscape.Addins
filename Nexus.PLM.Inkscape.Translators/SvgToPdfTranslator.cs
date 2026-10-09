using Nexus.PLM.Addin.Sdk.Translators;
using SkiaSharp;

namespace Nexus.PLM.Inkscape.Translators;

/// <summary>Wraps an Inkscape SVG drawing into a single-page vector PDF.</summary>
public sealed class SvgToPdfTranslator : ITranslator
{
    /// <inheritdoc/>
    public string Key => "svg_to_pdf";

    /// <inheritdoc/>
    public string Label => "SVG → PDF";

    /// <inheritdoc/>
    public string Description =>
        "Draws an SVG into a single-page vector PDF at its natural size. Pure .NET — no Inkscape needed on the server.";

    /// <inheritdoc/>
    public string InputMimeType => MimeTypes.Svg;

    /// <inheritdoc/>
    public string OutputMimeType => MimeTypes.Pdf;

    /// <inheritdoc/>
    public string OutputFileExtension => ".pdf";

    /// <inheritdoc/>
    public Task<Stream> TranslateAsync(Stream input, CancellationToken cancellationToken = default)
    {
        using var svg = SvgRenderer.Load(input);
        var size = SvgRenderer.SizeOf(svg);

        var ms = new MemoryStream();
        using (var document = SKDocument.CreatePdf(ms))
        {
            using var canvas = document.BeginPage(size.Width, size.Height);
            canvas.DrawPicture(svg.Picture);
            document.EndPage();
            document.Close();
        }

        ms.Position = 0;
        return Task.FromResult<Stream>(ms);
    }
}
